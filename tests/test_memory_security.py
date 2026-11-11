import json
from pathlib import Path
import tempfile
import unittest

from agent_server.core import Agent, Memory
from agent_server.security import Vault, encrypt_backup, decrypt_backup
from agent_server.skills import CATALOGUE


class MemorySecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'private.sqlite'
        self.vault = Vault(str(self.path) + '.key')
        self.memory = Memory(str(self.path), self.vault)
        self.memory.upsert('a', 'private-alias-marker', True, 'private-notes-marker')

    def tearDown(self):
        self.memory.db.close()
        self.temp.cleanup()

    def test_encrypted_fields_and_reopen(self):
        self.memory.set_fact('a', 'interest', 'private-fact-marker')
        self.memory.update_settings({'model_api_key': 'private-key-marker'})
        Agent(self.memory, lambda *_: 'private-reply-marker').decide('a', 'private-message-marker', 'one')
        with self.memory.lock:
            self.memory.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        data = self.path.read_bytes()
        for marker in ('private-alias-marker', 'private-notes-marker', 'private-fact-marker', 'private-key-marker', 'private-message-marker', 'private-reply-marker'):
            self.assertNotIn(marker.encode(), data)
        other = Memory(str(self.path), Vault(str(self.path) + '.key'))
        try:
            self.assertEqual(other.facts('a')['interest'], 'private-fact-marker')
            self.assertEqual(other.settings()['model_api_key'], 'private-key-marker')
            self.assertEqual(len(other.history('a')), 2)
        finally:
            other.db.close()

    def test_candidates_require_confirmation_and_scope(self):
        self.memory.upsert('b', 'B', True)
        agent = Agent(self.memory, lambda *_: '好呀')
        agent.decide('a', '我喜欢科幻电影', 'one')
        agent.decide('a', '我喜欢科幻电影', 'two')
        candidates = self.memory.candidates('a')
        self.assertEqual(len(candidates), 1)
        self.assertEqual(self.memory.facts('a'), {})
        with self.assertRaises(KeyError):
            self.memory.confirm_candidate('b', candidates[0]['id'], True)
        self.memory.confirm_candidate('a', candidates[0]['id'], True)
        self.memory.confirm_candidate('a', candidates[0]['id'], True)
        self.assertEqual(list(self.memory.facts('a').values()), ['科幻电影'])
        self.assertEqual(self.memory.facts('b'), {})

    def test_inferences_are_not_memory(self):
        Agent(self.memory, lambda *_: '你可能喜欢电影').decide('a', '今天有点累')
        self.assertEqual(self.memory.candidates('a'), [])
        self.assertEqual(self.memory.facts('a'), {})

    def test_backup_restores_candidates_and_requires_new_consent(self):
        Agent(self.memory, lambda *_: '好呀').decide('a', '我喜欢音乐')
        document = self.memory.backup_document()
        password = 'synthetic-password-for-test'
        envelope = encrypt_backup(document, password)
        self.assertNotIn('private-notes-marker', json.dumps(envelope))
        recovered = decrypt_backup(envelope, password)
        with self.assertRaises(Exception):
            decrypt_backup(envelope, 'wrong-password-for-test')
        self.memory.delete('a')
        self.assertEqual(self.memory.restore_document(recovered), 1)
        self.assertFalse(self.memory.contact('a')[2])
        self.assertEqual(len(self.memory.history('a')), 2)
        self.assertEqual(len(self.memory.candidates('a')), 1)

    def test_restore_conflict_rolls_back_every_contact(self):
        document = self.memory.backup_document()
        new = dict(document['contacts'][0], contact_id='new')
        document['contacts'].insert(0, new)
        with self.assertRaises(ValueError):
            self.memory.restore_document(document)
        self.assertIsNone(self.memory.contact('new'))

    def test_backup_restores_portable_settings_and_preserves_local_credentials(self):
        portable = {'model_base_url': 'https://api.deepseek.com', 'model_name': 'deepseek-chat',
                    'disabled_skills': ['humor-assistant'], 'personal_style': {'tone': '口语'}}
        self.memory.update_settings(dict(portable, model_api_key='old-key', auto_reply_enabled=True,
                                         astrbot_url='http://127.0.0.1:6185', bot_last_seen=123))
        document = self.memory.backup_document()
        self.assertEqual(document['settings'], portable)
        self.memory.delete('a')
        self.memory.update_settings({'model_name': 'other-model', 'model_api_key': 'local-key',
                                     'auto_reply_enabled': False, 'astrbot_url': 'http://127.0.0.1:9999'})
        # Older backups may include machine-local settings. They must stay local.
        document['settings'].update(model_api_key='backup-key', auto_reply_enabled=True,
                                    astrbot_url='http://127.0.0.1:6185', bot_last_seen=456)
        self.memory.restore_document(document)
        settings = self.memory.settings()
        self.assertEqual({key: settings[key] for key in portable}, portable)
        self.assertEqual(settings['model_api_key'], 'local-key')
        self.assertFalse(settings['auto_reply_enabled'])
        self.assertEqual(settings['astrbot_url'], 'http://127.0.0.1:9999')
        self.assertEqual(settings['bot_last_seen'], 123)

    def test_invalid_backup_settings_do_not_restore_contacts(self):
        document = self.memory.backup_document()
        document['settings'] = {'personal_style': {'tone': ['invalid']}}
        self.memory.delete('a')
        with self.assertRaises(ValueError):
            self.memory.restore_document(document)
        self.assertIsNone(self.memory.contact('a'))

    def test_backup_preserves_decay_and_processed_ids_after_reauthorization(self):
        import time
        self.memory.set_fact('a', 'interest', 'music')
        updated = int(time.time()) - 180 * 86400
        with self.memory.transaction() as db:
            db.execute('UPDATE facts SET updated_at=?', (updated,))
            db.execute('UPDATE fact_meta SET updated_at=?,weight=2', (updated,))
        Agent(self.memory, lambda *_: 'hello').decide('a', 'hi', 'delivered-message')
        document = self.memory.backup_document()
        self.memory.delete('a')
        self.memory.restore_document(document)
        self.assertEqual(self.memory.fact_details('a')[0]['updated_at'], updated)
        self.assertAlmostEqual(self.memory.fact_details('a')[0]['weight'], 1.0, places=3)
        self.memory.upsert('a', 'A', True)
        calls = []
        result = Agent(self.memory, lambda *_: calls.append(1) or 'duplicate').decide('a', 'hi', 'delivered-message')
        self.assertEqual(result['action'], 'handoff')
        self.assertEqual(calls, [])
        self.assertEqual(len(self.memory.history('a')), 2)

    def test_all_registered_skills_execute(self):
        self.assertIn('reply-quality-checker', CATALOGUE)
        self.assertGreaterEqual(len(CATALOGUE), 12)
        agent = Agent(self.memory, lambda *_: '已完成本次任务')
        for skill in CATALOGUE:
            with self.subTest(skill=skill):
                result = agent.decide('a', '今天怎么样', skill=skill)
                self.assertEqual(result['action'], 'draft')
                self.assertEqual(result['skills'][0], skill)

    def test_disabled_skill_and_personal_style(self):
        self.memory.update_settings({'disabled_skills': ['humor-assistant'], 'personal_style': {'tone': '口语'}})
        captured = []
        def model(prompt, _):
            captured.append(prompt)
            return '好的'
        agent = Agent(self.memory, model)
        self.assertEqual(agent.decide('a', '你好', skill='humor-assistant')['action'], 'handoff')
        self.assertEqual(captured, [])
        agent.decide('a', '你好', skill='personal-style')
        self.assertIn('口语', captured[0])

    def test_plain_legacy_storage_is_encrypted_on_adoption(self):
        path = Path(self.temp.name) / 'legacy.sqlite'
        old = Memory(str(path))
        old.upsert('old', 'legacy-sensitive-marker', True)
        old.db.close()
        protected = Memory(str(path), self.vault)
        try:
            self.assertEqual(protected.contact('old')[1], 'legacy-sensitive-marker')
            self.assertNotIn(b'legacy-sensitive-marker', path.read_bytes())
        finally:
            protected.db.close()


if __name__ == '__main__':
    unittest.main()
