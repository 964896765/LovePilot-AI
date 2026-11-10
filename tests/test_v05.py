import tempfile
import unittest
from agent_server.core import Agent, Memory

class ConsentLifecycleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.db=Memory(self.tmp.name+'/memory.sqlite')
  self.db.upsert('a','Alice',True,'电影')
  self.db.upsert('b','Bob',True,'音乐')
 def tearDown(self):
  self.db.db.close();self.tmp.cleanup()
 def test_revoke_blocks_even_cached_message(self):
  a=Agent(self.db,lambda *_:'你好')
  self.assertEqual(a.decide('a','在吗','one')['action'],'draft')
  self.db.revoke('a')
  self.assertEqual(a.decide('a','在吗','one')['action'],'handoff')
  self.assertIsNone(self.db.cached('a','one'))
 def test_export_is_contact_scoped(self):
  self.db.set_fact('a','喜欢','科幻')
  self.db.set_fact('b','喜欢','音乐')
  record=self.db.export('a')
  self.assertEqual(record['facts'],{'喜欢':'科幻'})
  self.assertNotIn('音乐',str(record))
 def test_delete_after_revoke(self):
  self.db.revoke('a');self.db.delete('a')
  self.assertIsNone(self.db.export('a'))
 def test_unconsented_contact_does_not_call_model(self):
  self.db.revoke('a')
  def fail(*_):raise AssertionError('model should not be called')
  self.assertEqual(Agent(self.db,fail).decide('a','你好')['action'],'handoff')

if __name__=='__main__':unittest.main()
