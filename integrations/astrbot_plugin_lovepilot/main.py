"""Explicit AI Bot bridge for AstrBot's official Tencent iLink adapter."""
import asyncio
from collections import OrderedDict
import hashlib
import os
from pathlib import Path
import time

import httpx
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .delivery import DeliveryStore


class RetryableDraft(Exception):
    """The backend did not commit this message and permits redelivery."""


class LovePilotBridge(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_url = os.getenv('LOVEPILOT_URL', 'http://127.0.0.1:8768').rstrip('/')
        self.token = os.getenv('LOVEPILOT_BOT_TOKEN') or os.getenv('LOVEPILOT_TOKEN', '')
        self.timeout = max(45, float(os.getenv('LOVEPILOT_TIMEOUT', '50')))
        self.auto_reply = os.getenv('LOVEPILOT_AUTO_REPLY', 'false').lower() == 'true'
        self.cooldown_seconds = max(1, float(os.getenv('LOVEPILOT_COOLDOWN_SECONDS', '3')))
        self._last_seen = OrderedDict()
        self.delivery = DeliveryStore(os.getenv('LOVEPILOT_BOT_STATE', str(Path.home() / '.lovepilot/bot-delivery.sqlite')))

    def _headers(self):
        return {'Authorization': 'Bearer ' + self.token}

    @staticmethod
    def _message_id(event):
        value = str(getattr(event.message_obj, 'message_id', '') or '')
        return hashlib.sha256(value.encode()).hexdigest() if len(value) > 120 else value

    async def _request(self, client, method, path, **kwargs):
        for attempt in range(2):
            try:
                response = await client.request(method, self.base_url + path, headers=self._headers(), **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if attempt or exc.response.status_code not in (429, 502, 503, 504):
                    raise
            except httpx.TransportError:
                if attempt:
                    raise
            await asyncio.sleep(0.5)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=100)
    async def on_private_message(self, event: AstrMessageEvent):
        if event.get_platform_name() != 'weixin_oc':
            return
        allowed = os.getenv('LOVEPILOT_BOT_PLATFORM_ID', '')
        if allowed and event.platform_meta.id != allowed:
            return
        event.stop_event()
        origin = str(event.unified_msg_origin)
        cid = origin if len(origin) <= 100 else 'weixin:' + hashlib.sha256(origin.encode()).hexdigest()
        mid = self._message_id(event)
        if not mid:
            await event.send(event.plain_result('当前消息缺少稳定标识，已交由管理员检查适配器。'))
            return
        scope = hashlib.sha256(origin.encode()).hexdigest()
        if not self.delivery.claim(scope, mid):
            return
        completed = False
        try:
            async for result in self._handle(event, cid, mid):
                await event.send(result)
            completed = True
        except RetryableDraft as exc:
            logger.warning('LovePilot model response permits retry')
            await event.send(event.plain_result(str(exc)))
        except httpx.HTTPStatusError as exc:
            logger.error('LovePilot API status=%s', exc.response.status_code)
            await event.send(event.plain_result('LovePilot 服务暂时不可用，请稍后重试。'))
        except Exception as exc:
            logger.error('LovePilot bridge failure type=%s', type(exc).__name__)
            await event.send(event.plain_result('LovePilot 连接失败，请稍后重试。'))
        finally:
            if not completed:
                self._last_seen.pop(cid, None)
            self.delivery.finish(scope, mid, completed)

    async def _handle(self, event, cid, mid):
        text = (event.message_str or '').strip()
        original = (getattr(event.message_obj, 'message_str', '') or '').strip()
        if original in ('/start', '/pause', '/forget', '/help'):
            text = original
        if text == '/help':
            yield event.plain_result('我是 LovePilot AI 机器人。\n/start 开启本会话\n/pause 暂停\n/forget 删除本会话资料\n/help 帮助\n支持文本与适配器提供的语音转写。图片理解和语音发送需另行配置。')
            return
        if not self.token:
            yield event.plain_result('LovePilot 服务访问令牌尚未配置，请联系管理员。')
            return
        if not text:
            yield event.plain_result('当前请发送文本，或使用微信提供的语音转写。')
            return
        async with httpx.AsyncClient(timeout=self.timeout, headers={'X-LovePilot-Origin': str(event.unified_msg_origin)}) as client:
            await self._request(client, 'POST', '/bot/heartbeat', json={})
            if text == '/start':
                await self._request(client, 'POST', '/contacts', json={
                    'contact_id': cid, 'alias': (event.get_sender_name() or '微信用户')[:100],
                    'consent': True, 'notes': '对方通过 /start 主动开启 AI Bot 对话。'})
                yield event.plain_result('你好，我是 LovePilot AI，一个 AI 聊天助手。\n已开启本会话。管理员启用自动回复后即可聊天。\n/pause 可暂停，/forget 可删除本会话记忆。')
                return
            if text in ('/pause', '/forget'):
                path = '/revoke' if text == '/pause' else '/delete'
                try:
                    await self._request(client, 'POST', path, json={'contact_id': cid})
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                yield event.plain_result('已暂停本会话。' if text == '/pause' else '已删除本会话的资料与记忆。')
                return
            if not self.auto_reply:
                return
            permit = await self._request(client, 'GET', '/bot/permit', params={'contact_id': cid})
            if not permit.get('consent') or not permit.get('auto_reply_enabled'):
                return
            now = time.monotonic()
            previous = self._last_seen.get(cid, 0)
            if now - previous < self.cooldown_seconds:
                yield event.plain_result('消息较密集，请稍等片刻再继续。')
                return
            self._last_seen[cid] = now
            self._last_seen.move_to_end(cid)
            if len(self._last_seen) > 2048:
                self._last_seen.popitem(last=False)
            result = await self._request(client, 'POST', '/draft', json={
                'contact_id': cid, 'message': text, 'message_id': mid, 'source': 'bot'})
            if result.get('action') == 'paused':
                return
            permit = await self._request(client, 'GET', '/bot/permit', params={'contact_id': cid})
            if not permit.get('consent') or not permit.get('auto_reply_enabled'):
                return
            if result.get('retryable'):
                raise RetryableDraft(result.get('reason') or '模型暂时不可用，请稍后重试。')
            if result.get('action') != 'draft':
                yield event.plain_result(result.get('reason', '这次请由本人处理。'))
                return
            reply = result.get('reply')
            if isinstance(reply, str) and reply.strip():
                yield event.plain_result(reply)

    async def terminate(self):
        self.delivery.close()
