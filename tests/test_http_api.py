"""HTTP regression coverage using a real child server and synthetic model output.

No external model or WeChat account is used by these tests.
"""
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


SERVER_RUNNER = """
import os
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from agent_server import server

server.agent.model = lambda prompt, history: 'synthetic-http-draft'
httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
worker = threading.Thread(target=httpd.serve_forever)
worker.start()
try:
    Path(os.environ['AUDIT_READY_FILE']).write_text(str(httpd.server_port))
    sys.stdin.buffer.read()
finally:
    httpd.shutdown()
    httpd.server_close()
    worker.join()
    server.memory.db.close()
"""


class HttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="lovepilot-http-test-")
        cls.token = secrets.token_urlsafe(32)
        cls.bot_token = secrets.token_urlsafe(32)
        cls.reader_token = secrets.token_urlsafe(32)
        ready = Path(cls.temp.name) / "ready"
        environment = os.environ.copy()
        environment.update(
            LOVEPILOT_TOKEN=cls.token,
            LOVEPILOT_BOT_TOKEN=cls.bot_token,
            LOVEPILOT_READ_TOKEN=cls.reader_token,
            LOVEPILOT_DB=str(Path(cls.temp.name) / "test.sqlite3"),
            AUDIT_READY_FILE=str(ready),
        )
        environment.pop("DEEPSEEK_API_KEY", None)
        cls.log = (Path(cls.temp.name) / "server.log").open("w+", encoding="utf-8")
        cls.process = subprocess.Popen(
            [sys.executable, "-u", "-c", SERVER_RUNNER],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdin=subprocess.PIPE,
            stdout=cls.log,
            stderr=cls.log,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if ready.exists() and ready.read_text().strip():
                cls.port = int(ready.read_text())
                return
            if cls.process.poll() is not None:
                break
            time.sleep(0.05)
        cls.process.communicate(input=b"", timeout=10)
        cls.log.seek(0)
        diagnostic = cls.log.read()
        cls.log.close()
        cls.temp.cleanup()
        raise RuntimeError("HTTP test server did not start. " + diagnostic)

    @classmethod
    def tearDownClass(cls):
        cls.process.communicate(input=b"", timeout=10)
        cls.log.close()
        cls.temp.cleanup()

    def setUp(self):
        self.contact_id = "http-test-" + uuid.uuid4().hex

    def tearDown(self):
        self.request("POST", "/delete", {"contact_id": self.contact_id})

    def request(self, method, path, data=None, token=None, raw_body=None, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = "Bearer " + (self.token if token is None else token)
        if origin:
            headers['X-LovePilot-Origin'] = origin
        body = json.dumps(data).encode("utf-8") if data is not None else raw_body
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def create_contact(self, consent=True):
        status, body = self.request("POST", "/contacts", {
            "contact_id": self.contact_id, "alias": "Synthetic contact",
            "consent": consent, "notes": "synthetic notes",
        })
        self.assertEqual((status, body), (200, {"ok": True}))

    def test_health(self):
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertIn("langgraph_available", body["adapters"])

    def test_skills(self):
        status, body = self.request("GET", "/skills")
        self.assertEqual(status, 200)
        self.assertIn("romance-reply", body["skills"])

    def test_unauthorized_get_and_post(self):
        for token in ["", "invalid"]:
            for method, path, data in [("GET", "/health", None),
                                       ("POST", "/contacts", {"contact_id": self.contact_id})]:
                with self.subTest(method=method, token=token):
                    self.assertEqual(self.request(method, path, data, token=token)[0], 401)

    def test_contact_and_facts_roundtrip(self):
        self.create_contact()
        self.assertEqual(self.request("POST", "/facts", {
            "contact_id": self.contact_id, "key": "interest", "value": "synthetic films",
        })[0], 200)
        status, body = self.request("GET", "/memory?contact_id=" + self.contact_id)
        self.assertEqual(status, 200)
        self.assertEqual(body["facts"], {"interest": "synthetic films"})
        self.assertEqual(body["history"], [])

    def test_draft_and_duplicate(self):
        self.create_contact()
        data = {"contact_id": self.contact_id, "message": "hello", "message_id": "one"}
        first = self.request("POST", "/draft", data)
        self.assertEqual(first[0], 200)
        self.assertEqual(first[1]["reply"], "synthetic-http-draft")
        self.assertTrue(first[1]["requires_confirmation"])
        self.assertEqual(self.request("POST", "/draft", data), first)
        history = self.request("GET", "/memory?contact_id=" + self.contact_id)[1]["history"]
        self.assertEqual(len(history), 2)

    def test_sensitive_handoff(self):
        self.create_contact()
        status, body = self.request("POST", "/draft", {
            "contact_id": self.contact_id, "message": "借钱",
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "handoff")

    def test_contact_isolation(self):
        self.create_contact()
        other_id = "http-test-" + uuid.uuid4().hex
        try:
            self.assertEqual(self.request("POST", "/contacts", {
                "contact_id": other_id, "alias": "Other synthetic contact", "consent": True,
            })[0], 200)
            self.assertEqual(self.request("POST", "/facts", {
                "contact_id": self.contact_id, "key": "private", "value": "marker-A",
            })[0], 200)
            self.assertEqual(self.request("POST", "/draft", {
                "contact_id": self.contact_id, "message": "private-message-A",
            })[0], 200)
            status, other = self.request("POST", "/export", {"contact_id": other_id})
            self.assertEqual(status, 200)
            self.assertEqual(other["facts"], {})
            self.assertEqual(other["history"], [])
            self.assertNotIn("marker-A", json.dumps(other))
        finally:
            self.request("POST", "/delete", {"contact_id": other_id})

    def test_unconsented_handoff(self):
        self.create_contact(consent=False)
        status, body = self.request("POST", "/draft", {
            "contact_id": self.contact_id, "message": "hello",
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "handoff")

    def test_revoke_invalidates_cached_draft(self):
        self.create_contact()
        data = {"contact_id": self.contact_id, "message": "hello", "message_id": "one"}
        self.assertEqual(self.request("POST", "/draft", data)[1]["action"], "draft")
        self.assertEqual(self.request("POST", "/revoke", {"contact_id": self.contact_id})[0], 200)
        self.assertEqual(self.request("POST", "/draft", data)[1]["action"], "handoff")

    def test_export_and_delete(self):
        self.create_contact()
        data = {"contact_id": self.contact_id}
        status, body = self.request("POST", "/export", data)
        self.assertEqual(status, 200)
        self.assertEqual(body["contact_id"], self.contact_id)
        self.assertEqual(self.request("POST", "/delete", data)[0], 200)
        self.assertEqual(self.request("POST", "/export", data)[0], 404)
        self.assertEqual(self.request("GET", "/memory?contact_id=" + self.contact_id)[0], 404)

    def test_missing_contact(self):
        for path in ["/facts", "/revoke", "/export", "/delete"]:
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path, {"contact_id": self.contact_id})[0], 404)

    def test_invalid_contact_and_consent(self):
        for data in [{"contact_id": ""}, {"contact_id": 123},
                     {"contact_id": self.contact_id, "consent": "true"}]:
            with self.subTest(data=data):
                self.assertEqual(self.request("POST", "/contacts", data)[0], 400)

    def test_invalid_json(self):
        self.assertEqual(self.request("POST", "/contacts", raw_body=b"{broken")[0], 400)
        self.assertEqual(self.request("POST", "/contacts", raw_body=b"[]")[0], 400)

    def test_invalid_fact(self):
        self.create_contact()
        self.assertEqual(self.request("POST", "/facts", {
            "contact_id": self.contact_id, "key": "", "value": "test",
        })[0], 400)

    def test_invalid_draft(self):
        self.create_contact()
        for fields in [{"message": ""}, {"message": "hello", "message_id": ""},
                       {"message": "hello", "message_id": 123}]:
            with self.subTest(fields=fields):
                self.assertEqual(self.request("POST", "/draft", {
                    "contact_id": self.contact_id, **fields,
                })[0], 400)

    def test_unknown_route(self):
        self.assertEqual(self.request("GET", "/missing")[0], 404)
        self.assertEqual(self.request("POST", "/missing", {"contact_id": self.contact_id})[0], 404)

    def test_management_read_endpoints(self):
        for path, key in [('/contacts', 'contacts'), ('/candidates', 'candidates'), ('/runs', 'runs'),
                          ('/logs', 'logs'), ('/status', 'workflow'), ('/settings', 'model_key_configured'),
                          ('/bot/status', 'auto_reply_enabled')]:
            with self.subTest(path=path):
                status, body = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertIn(key, body)

    def test_memory_query_supports_additional_parameters(self):
        self.create_contact()
        self.assertEqual(self.request('GET', '/memory?limit=1&contact_id=' + self.contact_id)[0], 200)
        self.assertEqual(self.request('GET', '/memory?contact_id=a&contact_id=b')[0], 400)

    def test_settings_validate_and_keep_secrets_private(self):
        status, _ = self.request('POST', '/settings', {'personal_style': {'tone': '口语'}, 'auto_reply_enabled': False})
        self.assertEqual(status, 200)
        settings = self.request('GET', '/settings')[1]
        self.assertEqual(settings['personal_style']['tone'], '口语')
        self.assertNotIn('model_api_key', settings)
        self.assertEqual(self.request('POST', '/settings', {'auto_reply_enabled': 'true'})[0], 400)
        self.assertEqual(self.request('POST', '/settings', {'personal_style': {'invented': 'guess'}})[0], 400)
        self.assertEqual(self.request('POST', '/settings', {'model_base_url': 'http://untrusted.example'})[0], 400)

    def test_bot_and_reader_token_scopes(self):
        self.assertEqual(self.request('GET', '/health', token=self.bot_token)[0], 200)
        self.assertEqual(self.request('GET', '/contacts', token=self.bot_token)[0], 403)
        self.assertEqual(self.request('POST', '/backup', {'password': 'synthetic-password'}, token=self.bot_token)[0], 403)
        self.assertEqual(self.request('GET', '/status', token=self.reader_token)[0], 200)
        self.assertEqual(self.request('POST', '/contacts', {'contact_id': self.contact_id}, token=self.reader_token)[0], 403)
        self.assertEqual(self.request('POST', '/contacts', {'contact_id': self.contact_id}, token=self.bot_token)[0], 403)
        origin = 'test-bot:FriendMessage:scope-test'
        try:
            data = {'contact_id': origin, 'alias': 'Bot participant', 'consent': True}
            self.assertEqual(self.request('POST', '/contacts', data, token=self.bot_token, origin=origin)[0], 200)
            self.assertEqual(self.request('GET', '/bot/permit?contact_id=' + self.contact_id, token=self.bot_token, origin=origin)[0], 403)
        finally:
            self.request('POST', '/delete', {'contact_id': origin})

    def test_candidate_confirmation_and_fact_delete(self):
        self.create_contact()
        self.request('POST', '/draft', {'contact_id': self.contact_id, 'message': '我喜欢音乐'})
        candidates = self.request('GET', '/candidates?contact_id=' + self.contact_id)[1]['candidates']
        self.assertEqual(len(candidates), 1)
        payload = {'contact_id': self.contact_id, 'candidate_id': candidates[0]['id'], 'approve': True}
        self.assertEqual(self.request('POST', '/candidates/confirm', payload)[0], 200)
        facts = self.request('GET', '/memory?contact_id=' + self.contact_id)[1]['facts']
        key = next(iter(facts))
        self.assertEqual(facts[key], '音乐')
        self.assertEqual(self.request('POST', '/facts/delete', {'contact_id': self.contact_id, 'key': key})[0], 200)
        self.assertEqual(self.request('GET', '/memory?contact_id=' + self.contact_id)[1]['facts'], {})

    def test_encrypted_backup_and_restore(self):
        self.create_contact()
        self.request('POST', '/facts', {'contact_id': self.contact_id, 'key': 'interest', 'value': 'music'})
        password = 'synthetic-backup-password'
        status, backup = self.request('POST', '/backup', {'password': password})
        self.assertEqual(status, 200)
        self.assertEqual(backup['format'], 'lovepilot-backup-v1')
        self.assertEqual(self.request('POST', '/restore', {'backup': backup, 'password': password, 'confirm': 'RESTORE'})[0], 400)
        self.request('POST', '/delete', {'contact_id': self.contact_id})
        status, result = self.request('POST', '/restore', {'backup': backup, 'password': password, 'confirm': 'RESTORE'})
        self.assertEqual(status, 200)
        self.assertTrue(result['consent_required'])
        record = self.request('POST', '/export', {'contact_id': self.contact_id})[1]
        self.assertFalse(record['consent'])
        self.assertEqual(record['facts'], {'interest': 'music'})

    def test_bot_global_pause_and_permit(self):
        self.create_contact()
        self.request('POST', '/settings', {'auto_reply_enabled': False})
        status, result = self.request('POST', '/draft', {'contact_id': self.contact_id, 'message': 'hello', 'source': 'bot'})
        self.assertEqual((status, result['action']), (200, 'paused'))
        self.assertFalse(self.request('GET', '/bot/permit?contact_id=' + self.contact_id)[1]['auto_reply_enabled'])
        self.assertEqual(self.request('POST', '/bot/heartbeat', {}, token=self.bot_token)[0], 200)
        self.assertEqual(self.request('GET', '/bot/status')[1]['state'], 'recent_event')

    def test_disabled_skill_rejects_generation(self):
        self.create_contact()
        self.request('POST', '/settings', {'disabled_skills': ['humor-assistant']})
        try:
            result = self.request('POST', '/draft', {'contact_id': self.contact_id, 'message': 'hello', 'skill': 'humor-assistant'})
            self.assertEqual(result[1]['action'], 'handoff')
        finally:
            self.request('POST', '/settings', {'disabled_skills': []})

    def test_sensitive_operations_require_confirmation(self):
        self.assertEqual(self.request('POST', '/data/delete', {'confirm': False})[0], 400)
        self.assertEqual(self.request('POST', '/restore', {'confirm': False})[0], 400)


if __name__ == "__main__":
    unittest.main()
