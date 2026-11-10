import tempfile, unittest
from agent_server.core import Memory, Agent
class TestV03(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.mem=Memory(self.tmp.name+'/m.db')
  self.mem.upsert('a','甲',True);self.mem.upsert('b','乙',True)
  self.calls=0
  def model(prompt,history):
   self.calls+=1;return '好呀'
  self.agent=Agent(self.mem,model)
 def tearDown(self):self.mem.db.close();self.tmp.cleanup()
 def test_idempotency(self):
  a=self.agent.decide('a','你好','msg1');b=self.agent.decide('a','你好','msg1')
  self.assertEqual(a,b);self.assertEqual(self.calls,1);self.assertEqual(len(self.mem.history('a')),2)
 def test_fact_isolation(self):
  self.mem.set_fact('a','兴趣','电影');self.assertEqual(self.mem.facts('a')['兴趣'],'电影');self.assertEqual(self.mem.facts('b'),{})
 def test_delete_cascade(self):
  self.mem.set_fact('a','兴趣','电影');self.agent.decide('a','你好','id1');self.mem.delete('a')
  self.assertEqual(self.mem.facts('a'),{});self.assertIsNone(self.mem.cached('a','id1'))
 def test_sensitive_no_model(self):
  self.assertEqual(self.agent.decide('a','不要再联系我','id2')['action'],'handoff');self.assertEqual(self.calls,0)
if __name__=='__main__':unittest.main()
