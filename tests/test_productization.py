import concurrent.futures
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent_server.core import Agent, Memory


class StorageRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "db.sqlite")
        self.memory = Memory(self.path)
        self.memory.upsert("a", "A", True)
        self.memory.upsert("b", "B", True)

    def tearDown(self):
        self.memory.db.close()
        self.temp.cleanup()

    def test_two_connections_deduplicate(self):
        other = Memory(self.path)
        calls = []
        def model(*_):
            calls.append(1)
            time.sleep(0.1)
            return "hello"
        agents = [Agent(self.memory, model), Agent(other, model)]
        try:
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda agent: agent.decide("a", "hi", "one"), agents))
            self.assertEqual(results[0], results[1])
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(self.memory.history("a")), 2)
        finally:
            other.db.close()

    def test_revoke_during_model_is_immediate(self):
        entered, release = threading.Event(), threading.Event()
        def model(*_):
            entered.set()
            release.wait(5)
            return "hello"
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            result = pool.submit(Agent(self.memory, model).decide, "a", "hi", "one")
            self.assertTrue(entered.wait(5))
            revoked = pool.submit(self.memory.revoke, "a")
            try:
                revoked.result(timeout=1)
            finally:
                release.set()
            self.assertEqual(result.result(5)["action"], "handoff")
        self.assertEqual(self.memory.history("a"), [])
        self.assertIsNone(self.memory.cached("a", "one"))

    def test_regrant_does_not_revive_inflight_request(self):
        def model(*_):
            self.memory.revoke("a")
            self.memory.upsert("a", "A", True)
            return "hello"
        self.assertEqual(Agent(self.memory, model).decide("a", "hi")["action"], "handoff")
        self.assertEqual(self.memory.history("a"), [])

    def test_delete_during_model_does_not_recreate_data(self):
        def model(*_):
            self.memory.delete("a")
            return "hello"
        self.assertEqual(Agent(self.memory, model).decide("a", "hi")["action"], "handoff")
        self.assertIsNone(self.memory.contact("a"))

    def test_error_can_retry_without_duplicate_history(self):
        def fail(*_):
            raise TimeoutError("synthetic")
        agent = Agent(self.memory, fail)
        self.assertTrue(agent.decide("a", "hi", "one")["retryable"])
        self.assertIsNone(self.memory.cached("a", "one"))
        agent.model = lambda *_: "recovered"
        self.assertEqual(agent.decide("a", "hi", "one")["reply"], "recovered")
        self.assertEqual(len(self.memory.history("a")), 2)

    def test_full_export_and_reopen(self):
        for index in range(1005):
            self.memory.add("a", "user", str(index))
        self.assertEqual(len(self.memory.export("a")["history"]), 1005)
        other = Memory(self.path)
        try:
            self.assertEqual(len(other.export("a")["history"]), 1005)
            self.assertGreaterEqual(other.db.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            other.db.close()

    def test_expired_lease_recovery(self):
        with self.memory.transaction() as db:
            db.execute("INSERT INTO leases VALUES(?,?,?)", ("a", "crashed-worker", time.time() - 1))
        self.assertEqual(Agent(self.memory, lambda *_: "hello").decide("a", "hi")["action"], "draft")

    def test_adopts_legacy_database(self):
        legacy_path = str(Path(self.temp.name) / "legacy.sqlite")
        connection = sqlite3.connect(legacy_path)
        connection.execute("CREATE TABLE contacts(id TEXT PRIMARY KEY,alias TEXT NOT NULL,consent INTEGER NOT NULL DEFAULT 0,notes TEXT NOT NULL DEFAULT '')")
        connection.execute("INSERT INTO contacts VALUES('old','Legacy',1,'preserved')")
        connection.commit()
        connection.close()
        legacy = Memory(legacy_path)
        try:
            self.assertEqual(legacy.contact("old")[3], "preserved")
            self.assertEqual(Agent(legacy, lambda *_: "hello").decide("old", "hi")["action"], "draft")
        finally:
            legacy.db.close()

    def test_production_graph_records_workflow(self):
        import json
        result = Agent(self.memory, lambda *_: "hello").decide("a", "hi", "trace")
        self.assertEqual(result["action"], "draft")
        row = self.memory.db.execute("SELECT trace FROM runs WHERE contact_id='a'").fetchone()
        names = [step["node"] for step in json.loads(row[0])]
        self.assertIn("emotion_analysis", names)
        self.assertIn("intent_analysis", names)
        self.assertIn("skill_route", names)
        self.assertIn("reply_review", names)
        self.assertEqual(names[-1], "memory_update")

    def test_old_message_is_not_regenerated_after_regrant(self):
        calls = []
        agent = Agent(self.memory, lambda *_: calls.append(1) or 'hello')
        agent.decide('a', 'hi', 'one')
        self.memory.revoke('a')
        self.memory.upsert('a', 'A', True)
        result = agent.decide('a', 'hi', 'one')
        self.assertEqual(result['action'], 'handoff')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.memory.history('a')), 2)

    def test_deleted_fact_is_excluded_from_future_context_and_cache(self):
        captured = []
        def model(prompt, history):
            captured.append((prompt, history))
            return 'hello'
        agent = Agent(self.memory, model)
        self.memory.set_fact('a', 'interest', 'private-interest-marker')
        agent.decide('a', 'I like private-interest-marker', 'one')
        self.memory.delete_fact('a', 'interest')
        self.assertIsNone(self.memory.cached('a', 'one'))
        agent.decide('a', 'hi', 'two')
        self.assertNotIn('private-interest-marker', str(captured[-1]))


if __name__ == "__main__":
    unittest.main()
