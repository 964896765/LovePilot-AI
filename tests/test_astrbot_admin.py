import base64
from pathlib import Path
import tempfile
import time
import unittest

import httpx
from agent_server.astrbot_admin import AstrBotAdmin
from agent_server.bot_runtime import credentials


class AstrBotAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        credentials(self.root)
        self.account = 'synthetic-account-one'
        self.created = []
        def handler(request):
            import json
            if request.url.path == '/api/v1/auth/login':
                return httpx.Response(200, json={'status': 'ok', 'data': {'token': 'synthetic-jwt'}})
            if request.url.path == '/api/v1/bot-types/weixin_oc/registration':
                body = json.loads(request.content)
                if body['action'] == 'start':
                    data = {'qrcode': 'synthetic-nonce', 'qrcode_img_content': 'https://example.com/test-qr', 'status': 'pending'}
                else:
                    data = {'status': 'created', 'weixin_oc_account_id': self.account,
                            'weixin_oc_token': 'synthetic-session-secret', 'weixin_oc_base_url': 'https://ilinkai.weixin.qq.com'}
                return httpx.Response(200, json={'status': 'ok', 'data': data})
            if request.url.path == '/api/v1/bots' and request.method == 'GET':
                return httpx.Response(200, json={'status': 'ok', 'data': []})
            if request.url.path == '/api/v1/bots' and request.method == 'POST':
                self.created.append(json.loads(request.content)['config'])
                return httpx.Response(200, json={'status': 'ok', 'data': None})
            return httpx.Response(404)
        self.client = httpx.Client(base_url='http://127.0.0.1:6185', transport=httpx.MockTransport(handler))
        self.admin = AstrBotAdmin(self.root, self.client)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_qr_image_is_real_png_and_excludes_upstream_session_secret(self):
        login = self.admin.start_login()
        self.assertTrue(base64.b64decode(login['qr_image_base64']).startswith(b'\x89PNG'))
        self.assertNotIn('synthetic-session-secret', str(login))

    def test_confirmed_login_is_created_once_and_sanitized(self):
        login = self.admin.start_login()
        first = self.admin.poll_login(login['session_id'])
        second = self.admin.poll_login(login['session_id'])
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'created')
        self.assertEqual(len(self.created), 1)
        self.assertNotIn('synthetic-session-secret', str(first))

    def test_accounts_have_separate_platform_namespaces(self):
        first = self.admin.poll_login(self.admin.start_login()['session_id'])
        self.account = 'synthetic-account-two'
        second = self.admin.poll_login(self.admin.start_login()['session_id'])
        self.assertNotEqual(first['bot_id'], second['bot_id'])

    def test_expired_and_unknown_sessions(self):
        login = self.admin.start_login()
        self.admin.sessions[login['session_id']]['expires_at'] = time.time() - 1
        self.assertEqual(self.admin.poll_login(login['session_id']), {'status': 'expired'})
        with self.assertRaises(KeyError):
            self.admin.poll_login('unknown')


if __name__ == '__main__':
    unittest.main()
