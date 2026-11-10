import tempfile
import unittest
from unittest.mock import patch
from agent_server.core import Agent, Memory
from agent_server.mem0_adapter import Mem0Adapter

class V06Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Memory(self.tmp.name + '/test.sqlite')
        self.db.upsert('a', 'A', True, '喜欢电影')
        self.db.upsert('b', 'B', False, '')
        self.agent = Agent(self.db, lambda prompt, history: '今天过得怎么样？')
    def tearDown(self):
        self.db.db.close()
        self.tmp.cleanup()
    def test_graph_draft(self):
        try:
            from agent_server.graph_adapter import build_graph
            graph = build_graph(self.agent)
        except ImportError:
            self.skipTest('langgraph not installed')
        result = graph.invoke({'contact_id':'a', 'message':'你好', 'message_id':'m1'})
        self.assertEqual(result['result']['action'], 'draft')
        self.assertIn('facts', result['context'])
    def test_graph_consent_guard(self):
        try:
            from agent_server.graph_adapter import build_graph
            graph = build_graph(self.agent)
        except ImportError:
            self.skipTest('langgraph not installed')
        self.assertEqual(graph.invoke({'contact_id':'b','message':'你好'})['result']['action'], 'handoff')
    def test_graph_sensitive_guard(self):
        try:
            from agent_server.graph_adapter import build_graph
            graph = build_graph(self.agent)
        except ImportError:
            self.skipTest('langgraph not installed')
        self.assertEqual(graph.invoke({'contact_id':'a','message':'借钱'})['result']['action'], 'handoff')
    def test_mem0_requires_consent(self):
        adapter = object.__new__(Mem0Adapter)
        with self.assertRaises(PermissionError):
            adapter.add_consented_fact('a', '电影')
        with self.assertRaises(PermissionError):
            adapter.search('a', '电影')
    def test_draft_does_not_send(self):
        result = self.agent.decide('a','你好')
        self.assertTrue(result['requires_confirmation'])
        self.assertEqual(result['action'], 'draft')

if __name__ == '__main__': unittest.main()
