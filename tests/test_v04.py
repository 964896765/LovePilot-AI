import unittest, tempfile
from agent_server.core import Agent,Memory

class TestV04(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.db=Memory(self.tmp.name+'/db.sqlite')
 def tearDown(self):
  self.db.db.close();self.tmp.cleanup()
 def test_facts_are_in_prompt(self):
  self.db.upsert('a','A',True,'喜欢电影')
  self.db.set_fact('a','共同话题','科幻电影')
  captured=[]
  def model(prompt,history):captured.append(prompt);return '最近看电影了吗？'
  result=Agent(self.db,model).decide('a','最近忙吗')
  self.assertEqual(result['action'],'draft')
  self.assertIn('科幻电影',captured[0])
 def test_isolation(self):
  self.db.upsert('a','A',True,'');self.db.upsert('b','B',True,'')
  self.db.set_fact('a','兴趣','电影')
  self.assertEqual(self.db.facts('b'),{})
 def test_handoff(self):
  self.db.upsert('a','A',True,'')
  self.assertEqual(Agent(self.db,lambda *_:'ok').decide('a','不要再联系我')['action'],'handoff')
 def test_duplicate(self):
  self.db.upsert('a','A',True,'')
  calls=[]
  def model(*args):calls.append(1);return '好的'
  a=Agent(self.db,model)
  a.decide('a','你好','m1');a.decide('a','你好','m1')
  self.assertEqual(len(calls),1)
 def test_delete(self):
  self.db.upsert('a','A',True,'');self.db.set_fact('a','兴趣','音乐');self.db.delete('a')
  self.assertIsNone(self.db.contact('a'))
  self.assertEqual(self.db.facts('a'),{})
if __name__=='__main__':unittest.main()
