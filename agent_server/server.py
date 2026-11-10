"""Authenticated local Agent API. Deploy remote access behind a TLS proxy."""
from collections import defaultdict, deque
import hmac
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import InvalidToken
from cryptography.exceptions import InvalidTag
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
os.environ.setdefault('MEM0_TELEMETRY', 'false')
os.environ.setdefault('FASTEMBED_CACHE_PATH', str(ROOT / 'data/models'))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')

from .core import Agent, Memory, optional_adapters
from .graph_adapter import build_graph
from .security import Vault
from .semantic import SemanticMemory
from .service import Service

logger = logging.getLogger(__name__)
default_db = 'lovepilot.sqlite3' if (ROOT / 'lovepilot.sqlite3').exists() else 'data/lovepilot.sqlite3'
db_path = Path(os.getenv('LOVEPILOT_DB', default_db))
if not db_path.is_absolute():
    db_path = ROOT / db_path
memory = Memory(str(db_path), vault=Vault(str(db_path) + '.key'))
agent = Agent(memory)
agent.graph = build_graph(agent)
semantic = SemanticMemory(memory, agent.model_client.config)
agent.semantic = semantic
service = Service(memory, agent, semantic)
TOKEN = os.getenv('LOVEPILOT_TOKEN', '')
BOT_TOKEN = os.getenv('LOVEPILOT_BOT_TOKEN', '')
READ_TOKEN = os.getenv('LOVEPILOT_READ_TOKEN', '')
BOT_GET = {'/health', '/skills', '/bot/status', '/bot/permit'}
BOT_POST = {'/contacts', '/draft', '/revoke', '/delete', '/bot/heartbeat'}


class Handler(BaseHTTPRequestHandler):
    _rate_lock = threading.Lock()
    _requests = defaultdict(deque)

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Query values can contain personal identifiers. Record only the path.
        logger.info('HTTP method=%s path=%s', self.command, urlsplit(self.path).path)

    def respond(self, code, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            logger.info('Client disconnected')

    def role(self):
        value = self.headers.get('Authorization', '')
        for role, token in [('admin', TOKEN), ('bot', BOT_TOKEN), ('reader', READ_TOKEN)]:
            if token and hmac.compare_digest(value.encode(), ('Bearer ' + token).encode()):
                return role
        return None

    def authorize(self, path):
        role = self.role()
        if not role:
            self.respond(401, {'error': 'unauthorized'})
            return False
        if role == 'reader' and self.command != 'GET':
            self.respond(403, {'error': 'read only token'})
            return False
        if role == 'bot' and path not in (BOT_GET if self.command == 'GET' else BOT_POST):
            self.respond(403, {'error': 'bot scope denied'})
            return False
        with self._rate_lock:
            window = self._requests[role]
            now = time.monotonic()
            while window and window[0] < now - 60:
                window.popleft()
            if len(window) >= 240:
                self.respond(429, {'error': 'rate limited', 'retryable': True})
                return False
            window.append(now)
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.authorize(path):
            return
        try:
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if self.role() == 'bot' and path == '/bot/permit' and not self.bot_contact_allowed(query.get('contact_id', [''])[0]):
                return self.respond(403, {'error': 'bot contact scope denied'})
            if path == '/health':
                return self.respond(200, {'ok': True, 'adapters': optional_adapters(), 'version': '2.0.0-dev'})
            return self.respond(200, service.get(path, query))
        except KeyError:
            return self.respond(404, {'error': 'not found'})
        except PermissionError as exc:
            return self.respond(403, {'error': str(exc)})
        except (ValueError, TypeError):
            return self.respond(400, {'error': 'invalid query'})
        except Exception as exc:
            logger.error('GET failed type=%s', type(exc).__name__)
            return self.respond(500, {'error': 'operation failed'})

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self.authorize(path):
            return
        try:
            maximum = 64 * 1024 * 1024 if path == '/restore' else 65536
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > maximum or self.headers.get('Transfer-Encoding'):
                return self.respond(413, {'error': 'invalid body size'})
            raw = self.rfile.read(length)
            if len(raw) != length:
                return self.respond(400, {'error': 'incomplete request'})
            data = json.loads(raw)
            if not isinstance(data, dict):
                return self.respond(400, {'error': 'JSON object required'})
            if self.role() == 'bot' and path != '/bot/heartbeat' and not self.bot_contact_allowed(data.get('contact_id', '')):
                return self.respond(403, {'error': 'bot contact scope denied'})
            if self.role() == 'bot' and path == '/draft':
                data['source'] = 'bot'
            if path == '/admin/shutdown':
                if self.role() != 'admin' or data.get('confirm') != 'STOP_AGENT':
                    return self.respond(403, {'error': 'admin confirmation required'})
                self.respond(200, {'ok': True, 'state': 'stopping'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            return self.respond(200, service.post(path, data))
        except (ValueError, TypeError, UnicodeError, InvalidTag, InvalidToken):
            return self.respond(400, {'error': 'invalid request or backup password'})
        except KeyError:
            return self.respond(404, {'error': 'not found'})
        except PermissionError as exc:
            return self.respond(403, {'error': str(exc)})
        except (socket.timeout, TimeoutError):
            return self.respond(408, {'error': 'request timeout', 'retryable': True})
        except sqlite3.IntegrityError:
            return self.respond(409, {'error': 'data conflict'})
        except Exception as exc:
            logger.error('POST failed type=%s', type(exc).__name__)
            return self.respond(500, {'error': 'operation failed'})

    def bot_contact_allowed(self, cid):
        origin = self.headers.get('X-LovePilot-Origin', '')
        platform_id = os.getenv('LOVEPILOT_BOT_PLATFORM_ID', '')
        if ':FriendMessage:' not in origin or len(origin) > 2000 or not isinstance(cid, str):
            return False
        if platform_id and not origin.startswith(platform_id + ':'):
            return False
        expected = origin if len(origin) <= 100 else 'weixin:' + hashlib.sha256(origin.encode()).hexdigest()
        return hmac.compare_digest(cid.encode(), expected.encode())


class AgentHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.capacity = threading.BoundedSemaphore(32)

    def process_request(self, request, address):
        if not self.capacity.acquire(blocking=False):
            request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.capacity.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.capacity.release()


if __name__ == '__main__':
    if len(TOKEN) < 24:
        raise SystemExit('请配置至少 24 字符的 LOVEPILOT_TOKEN')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    semantic.start()
    server = AgentHTTPServer(('127.0.0.1', int(os.getenv('LOVEPILOT_PORT', '8768'))))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        semantic.close()
        memory.db.close()
