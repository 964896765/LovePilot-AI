import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock
from types import SimpleNamespace


@unittest.skipUnless(importlib.util.find_spec("astrbot"), "Install the pinned AstrBot SDK to run bridge tests")
class BridgeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory()
        cls.environment = patch.dict(os.environ, {"ASTRBOT_ROOT": cls.root.name, "ASTRBOT_DISABLE_METRICS": "1", "LOVEPILOT_BOT_STATE": str(Path(cls.root.name) / 'delivery.sqlite')})
        cls.environment.start()
        import httpx
        from astrbot.api.star import Context
        from integrations.astrbot_plugin_lovepilot import main
        cls.httpx, cls.plugin = httpx, main
        cls.context = Context(*[None for _ in range(11)])

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.root.cleanup()

    def event(self, text="hi", session="test", mid="message-one", platform="weixin_oc"):
        from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType, PlatformMetadata
        from astrbot.core.platform.sources.weixin_oc.weixin_oc_event import WeixinOCMessageEvent
        message = AstrBotMessage()
        message.type = MessageType.FRIEND_MESSAGE
        message.self_id, message.session_id, message.message_id = "bot", session, mid
        message.message_str, message.message = text, []
        message.sender = MessageMember("user", "Test user")
        return WeixinOCMessageEvent(text, message, PlatformMetadata(platform, "test", "test-platform"), session, SimpleNamespace(send_by_session=AsyncMock()))

    def bridge(self):
        bridge = self.plugin.LovePilotBridge(self.context)
        bridge.token = "synthetic-test-token"
        bridge.cooldown_seconds = 0
        bridge.auto_reply = True
        self.instances.append(bridge)
        return bridge

    def setUp(self):
        self.instances = []

    async def asyncTearDown(self):
        for bridge in self.instances:
            await bridge.terminate()

    async def dispatch(self, bridge, event, handler):
        client = self.httpx.AsyncClient
        def respond(request):
            if request.url.path == '/bot/heartbeat':
                return self.httpx.Response(200, json={'ok': True})
            if request.url.path == '/bot/permit':
                return self.httpx.Response(200, json={'consent': True, 'auto_reply_enabled': True})
            return handler(request)
        with patch.object(self.plugin.httpx, "AsyncClient", side_effect=lambda **kwargs: client(transport=self.httpx.MockTransport(respond), **kwargs)):
            await bridge.on_private_message(event)
            return [call.args[1] for call in event.platform.send_by_session.call_args_list]

    async def test_real_sdk_message_id_and_event_stop(self):
        import json
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return self.httpx.Response(200, json={"action": "draft", "reply": "test"})
        event = self.event(mid='sdk-id-test')
        results = await self.dispatch(self.bridge(), event, handler)
        self.assertEqual(captured[0]["message_id"], "sdk-id-test")
        self.assertTrue(event.is_stopped())
        self.assertEqual(len(results), 1)

    async def test_http_error_has_fallback(self):
        results = await self.dispatch(self.bridge(), self.event(), lambda _: self.httpx.Response(503))
        self.assertEqual(len(results), 1)

    async def test_long_sessions_do_not_collide(self):
        import json
        captured = []
        def handler(request):
            captured.append(json.loads(request.content)["contact_id"])
            return self.httpx.Response(200, json={"action": "handoff"})
        bridge = self.bridge()
        await self.dispatch(bridge, self.event(session="x" * 110 + "A"), handler)
        await self.dispatch(bridge, self.event(session="x" * 110 + "B"), handler)
        self.assertNotEqual(captured[0], captured[1])
        self.assertLessEqual(len(captured[0]), 100)

    async def test_other_platform_is_ignored(self):
        event = self.event(platform="other")
        await self.bridge().on_private_message(event)
        results = event.platform.send_by_session.call_args_list
        self.assertEqual(results, [])
        self.assertFalse(event.is_stopped())

    async def test_duplicate_after_bridge_restart_is_not_sent(self):
        bridge = self.bridge()
        handler = lambda _: self.httpx.Response(200, json={'action': 'draft', 'reply': 'test'})
        first = self.event(mid='persistent-duplicate')
        self.assertEqual(len(await self.dispatch(bridge, first, handler)), 1)
        restarted = self.bridge()
        second = self.event(mid='persistent-duplicate')
        self.assertEqual(await self.dispatch(restarted, second, handler), [])

    async def test_retryable_model_failure_can_redeliver_same_id(self):
        bridge = self.bridge()
        bridge.cooldown_seconds = 3
        mid = 'retryable-model-failure'
        failure = lambda _: self.httpx.Response(200, json={
            'action': 'handoff', 'reason': 'temporary failure', 'retryable': True})
        self.assertEqual(len(await self.dispatch(bridge, self.event(mid=mid), failure)), 1)
        recovered = lambda _: self.httpx.Response(200, json={'action': 'draft', 'reply': 'recovered'})
        self.assertEqual(len(await self.dispatch(bridge, self.event(mid=mid), recovered)), 1)
        self.assertEqual(await self.dispatch(self.bridge(), self.event(mid=mid), recovered), [])

    async def test_commands_survive_official_wake_prefix_removal(self):
        expected = {'/start': '/contacts', '/pause': '/revoke', '/forget': '/delete', '/help': None}
        bridge = self.bridge()
        bridge.auto_reply = False
        for command, path in expected.items():
            with self.subTest(command=command):
                calls = []
                def handler(request):
                    calls.append(request.url.path)
                    return self.httpx.Response(200, json={'ok': True})
                event = self.event(text=command, mid='wake-prefix-' + command)
                event.message_str = command.removeprefix('/')
                self.assertEqual(len(await self.dispatch(bridge, event, handler)), 1)
                self.assertEqual(calls, [path] if path else [])

    async def test_pause_during_draft_prevents_send(self):
        bridge = self.bridge()
        client = self.httpx.AsyncClient
        permits = []
        def handler(request):
            if request.url.path == '/bot/heartbeat':
                return self.httpx.Response(200, json={'ok': True})
            if request.url.path == '/bot/permit':
                permits.append(1)
                return self.httpx.Response(200, json={'consent': len(permits) == 1, 'auto_reply_enabled': True})
            return self.httpx.Response(200, json={'action': 'draft', 'reply': 'test'})
        event = self.event(mid='pause-race')
        with patch.object(self.plugin.httpx, 'AsyncClient', side_effect=lambda **kwargs: client(transport=self.httpx.MockTransport(handler), **kwargs)):
            await bridge.on_private_message(event)
        self.assertEqual(event.platform.send_by_session.call_count, 0)


if __name__ == "__main__":
    unittest.main()
