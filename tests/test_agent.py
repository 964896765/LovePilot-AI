import tempfile, unittest
from agent_server.core import Agent,Memory,SKILLS
class TestAgent(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.m=Memory(self.tmp.name+'/test.db');self.a=Agent(self.m,lambda p,h:'好呀，今天过得怎么样？')
 def tearDown(self):self.m.db.close();self.tmp.cleanup()
 def test_no_consent(self):self.assertEqual(self.a.decide('x','你好')['action'],'handoff')
 def test_draft_and_memory(self):
  self.m.upsert('x','测试',True,'喜欢电影');r=self.a.decide('x','你好');self.assertEqual(r['action'],'draft');self.assertEqual(len(self.m.history('x')),2)
 def test_sensitive(self):
  self.m.upsert('x','测试',True);self.assertEqual(self.a.decide('x','别联系我')['action'],'handoff')
 def test_isolation(self):
  self.m.upsert('x','甲',True);self.m.upsert('y','乙',True);self.a.decide('x','你好');self.assertEqual(self.m.history('y'),[])
 def test_delete(self):
  self.m.upsert('x','甲',True);self.a.decide('x','你好');self.m.delete('x');self.assertIsNone(self.m.contact('x'))
 def test_skills(self):self.assertEqual(len(SKILLS),8)
if __name__=='__main__':unittest.main()
