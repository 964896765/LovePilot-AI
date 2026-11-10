"""Authenticated management through the official local AstrBot REST API."""
import base64
import hashlib
from io import BytesIO
from pathlib import Path
import secrets
import threading
import time

import httpx

from .bot_runtime import credentials


class AstrBotAdmin:
    def __init__(self, root=None, client=None):
        self.root = root or Path(__file__).resolve().parents[1] / 'data/astrbot'
        self.client = client or httpx.Client(base_url='http://127.0.0.1:6185', timeout=35, trust_env=False)
        self.token = None
        self.sessions = {}
        self.lock = threading.RLock()

    def request(self, method, path, **kwargs):
        with self.lock:
            if not self.token:
                if not (self.root / 'dashboard-credentials.enc').exists():
                    raise RuntimeError('Start AstrBot first')
                response = self.client.post('/api/v1/auth/login', json=credentials(self.root))
                response.raise_for_status()
                self.token = response.json()['data']['token']
            response = self.client.request(method, '/api/v1' + path, headers={'Authorization': 'Bearer ' + self.token}, **kwargs)
            if response.status_code == 401:
                self.token = None
            response.raise_for_status()
            envelope = response.json()
            if envelope.get('status') != 'ok':
                raise RuntimeError('AstrBot operation failed')
            return envelope.get('data')

    def start_login(self):
        import qrcode
        config = {'id': 'lovepilot_weixin', 'type': 'weixin_oc', 'enable': True}
        data = self.request('POST', '/bot-types/weixin_oc/registration', json={'action': 'start', 'platform_config': config})
        content = data['qrcode_img_content']
        image = qrcode.make(content)
        output = BytesIO()
        image.save(output, format='PNG')
        session = secrets.token_urlsafe(24)
        with self.lock:
            self.sessions = {key: value for key, value in self.sessions.items() if value['expires_at'] > time.time()}
            if len(self.sessions) >= 16:
                raise RuntimeError('Too many active QR sessions')
            self.sessions[session] = {'qrcode': data['qrcode'], 'platform_config': config, 'expires_at': time.time() + 240}
        return {'session_id': session, 'status': 'pending', 'qr_image_base64': base64.b64encode(output.getvalue()).decode(),
                'expires_at': self.sessions[session]['expires_at']}

    def poll_login(self, session):
        with self.lock:
            saved = self.sessions.get(session)
            if not saved:
                raise KeyError('login session not found')
            if saved.get('bot_id'):
                return {'status': 'created', 'bot_id': saved['bot_id']}
            if saved['expires_at'] <= time.time():
                return {'status': 'expired'}
            data = self.request('POST', '/bot-types/weixin_oc/registration', json={
                'action': 'poll', 'qrcode': saved['qrcode'], 'platform_config': saved['platform_config']})
            if data.get('status') == 'created':
                account = data.get('weixin_oc_account_id')
                if not isinstance(account, str) or not account:
                    raise ValueError('account identity missing')
                bot_id = 'lovepilot_' + hashlib.sha256(account.encode()).hexdigest()[:12]
                config = dict(saved['platform_config'], id=bot_id, name='LovePilot AI')
                for field in ('weixin_oc_token', 'weixin_oc_account_id', 'weixin_oc_base_url', 'weixin_oc_user_id'):
                    config[field] = data.get(field, '')
                bots = self.request('GET', '/bots') or []
                if isinstance(bots, dict):
                    bots = bots.get('bots', bots.get('platforms', []))
                exists = any(item.get('id') == bot_id for item in bots)
                if exists:
                    self.request('PUT', '/bots/by-id', params={'id': bot_id}, json={'config': config})
                else:
                    self.request('POST', '/bots', json={'config': config})
                saved['bot_id'] = bot_id
                return {'status': 'created', 'bot_id': bot_id}
            return {'status': data.get('status', 'pending'), 'qr_status': data.get('qr_status', 'wait')}
