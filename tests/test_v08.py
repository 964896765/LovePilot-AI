import json, tempfile, threading, unittest
from pathlib import Path
from agent_server.core import Agent, Memory

class V08Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.m=Memory(str(Path(self.tmp.name)/'test.sqlite3'))
  self.m.upsert('a','A',True,'')
  self.calls=0
  def model(prompt,history):
   self.calls+=1
   return '你好，最近怎么样？'
  self.agent=Agent(self.m,model)
 def tearDown(self):
  self.m.db.close();self.tmp.cleanup()
 def test_duplicate_message_is_idempotent(self):
  self.agent.decide('a','你好','same')
  self.agent.decide('a','你好','same')
  self.assertEqual(self.calls,1)
  self.assertEqual(len(self.m.history('a')),2)
 def test_concurrent_duplicate(self):
  threads=[threading.Thread(target=lambda:self.agent.decide('a','你好','parallel')) for _ in range(8)]
  [t.start() for t in threads]
  [t.join() for t in threads]
  self.assertEqual(self.calls,1)
 def test_revoke_via_upsert_clears_cache(self):
  self.agent.decide('a','你好','m1')
  self.m.upsert('a','A',False,'')
  self.assertEqual(self.agent.decide('a','你好','m1')['action'],'handoff')
  self.assertIsNone(self.m.cached('a','m1'))
 def test_delete_erases_audit(self):
  self.agent.decide('a','你好','m1')
  self.m.delete('a')
  self.assertEqual(self.m.db.execute('SELECT count(*) FROM audit WHERE contact_id=?',('a',)).fetchone()[0],0)
 def test_model_error_does_not_expose_secret(self):
  a=Agent(self.m,lambda p,h: (_ for _ in ()).throw(RuntimeError('secret-token-123')))
  self.assertNotIn('secret-token-123',json.dumps(a.decide('a','你好')))

if __name__=='__main__':unittest.main()
