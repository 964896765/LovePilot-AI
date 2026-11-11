import json
from pathlib import Path
import tempfile
import unittest

from agent_server.core import Agent, Memory


def generation():
    return {'reply_options': [
        {'id': 'gentle', 'text': '看到你的消息啦，今天过得怎么样？', 'reason': '回应原话并留下交流空间'},
        {'id': 'humor', 'text': '消息接收成功，聊天频道已打开。', 'reason': '采用轻松表达'},
        {'id': 'flirting', 'text': '看到你找我，想多听你说几句。', 'reason': '表达关心并保留边界'}],
        'analysis': {'facts': ['对方发来一条消息'], 'inferences': ['可能希望获得回应'], 'unknowns': ['对方此刻的实际心情']}}


class ReplyOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Memory(str(Path(self.temp.name) / 'options.sqlite'))
        self.memory.upsert('a', 'A', True)
        self.memory.upsert('b', 'B', True)
        self.captured = []
        self.output = generation()
        def model(prompt, history):
            self.captured.append((prompt, history))
            return json.dumps(self.output, ensure_ascii=False)
        self.agent = Agent(self.memory, model)

    def tearDown(self):
        self.memory.db.close()
        self.temp.cleanup()

    def test_three_options_are_reviewed_scoped_and_idempotent(self):
        result = self.agent.decide('a', '你好', 'one', reply_mode='three_options')
        self.assertEqual(result['action'], 'draft')
        self.assertEqual(len(result['reply_options']), 3)
        self.assertEqual(result['reply'], result['reply_options'][0]['text'])
        self.assertTrue(result['requires_confirmation'])
        self.assertTrue(result['analysis']['uncertain'])
        self.assertEqual(result['quality_check']['checked_options'], 3)
        self.assertEqual(self.agent.decide('a', '你好', 'one', reply_mode='three_options'), result)
        self.assertEqual(len(self.captured), 1)
        self.assertEqual(len(self.memory.history('a')), 2)
        self.assertEqual(self.memory.history('b'), [])

    def test_regeneration_and_refinement_do_not_duplicate_history(self):
        self.agent.decide('a', '你好', 'one', reply_mode='three_options')
        self.output['reply_options'][0]['text'] = '嗨，很高兴看到你的消息。'
        result = self.agent.decide('a', '你好', 'two', reply_mode='three_options', regenerate=True, refinement='shorter')
        self.assertEqual(result['action'], 'draft')
        self.assertEqual(len(self.memory.history('a')), 2)
        self.assertEqual(len(self.memory.runs('a')), 2)
        self.assertIn('缩短每条建议', self.captured[-1][0])

    def test_invalid_options_are_retryable_and_do_not_write_history(self):
        invalid = []
        duplicate = generation()
        duplicate['reply_options'][1]['text'] = duplicate['reply_options'][0]['text']
        invalid.append(duplicate)
        missing = generation()
        missing['reply_options'].pop()
        invalid.append(missing)
        bad_analysis = generation()
        bad_analysis['analysis']['facts'] = 'unsupported'
        invalid.append(bad_analysis)
        for index, output in enumerate(invalid):
            with self.subTest(index=index):
                self.output = output
                result = self.agent.decide('a', '你好', 'bad-' + str(index), reply_mode='three_options')
                self.assertTrue(result['retryable'])
                self.assertEqual(self.memory.history('a'), [])
                self.assertIsNone(self.memory.cached('a', 'bad-' + str(index)))
        self.output = generation()
        self.assertEqual(self.agent.decide('a', '你好', 'bad-0', reply_mode='three_options')['action'], 'draft')

    def test_every_candidate_is_checked_for_sensitive_commitments(self):
        self.output['reply_options'][2]['text'] = '我们结婚吧'
        result = self.agent.decide('a', '你好', 'sensitive', reply_mode='three_options')
        self.assertEqual(result['action'], 'handoff')
        self.assertNotIn('reply_options', result)
        self.assertNotIn('我们结婚吧', json.dumps(self.memory.history('a'), ensure_ascii=False))

    def test_new_sensitive_topics_handoff_before_model_call(self):
        for message in ('我们复合吧', '我现在胸痛', '这是我的银行卡', '你是不是有误会'):
            with self.subTest(message=message):
                self.assertEqual(self.agent.decide('a', message, reply_mode='three_options')['action'], 'handoff')
        self.assertEqual(self.captured, [])

    def test_modes_and_refinements_are_validated(self):
        with self.assertRaises(ValueError):
            self.agent.decide('a', '你好', reply_mode='unlimited')
        with self.assertRaises(ValueError):
            self.agent.decide('a', '你好', refinement='invented')

    def test_confirmed_personal_style_is_in_options_prompt(self):
        self.memory.update_settings({'personal_style': {'flirting': '关闭', 'questions': '避免追问'}})
        self.agent.decide('a', '你好', reply_mode='three_options')
        self.assertIn('避免追问', self.captured[0][0])
        self.assertIn('关闭', self.captured[0][0])

    def test_global_pause_prevents_generation_and_cannot_replay_cached_reply(self):
        self.agent.decide('a', '你好', 'one', reply_mode='three_options')
        self.memory.update_settings({'processing_paused': True})
        self.assertEqual(self.agent.decide('a', '你好', 'one')['action'], 'paused')
        self.assertEqual(len(self.captured), 1)
        self.memory.update_settings({'processing_paused': False})
        result = self.agent.decide('a', '你好', 'one')
        self.assertEqual(result['action'], 'handoff')
        self.assertEqual(len(self.captured), 1)

    def test_pause_and_resume_during_generation_discards_old_response(self):
        def model(*_):
            self.memory.update_settings({'processing_paused': True})
            self.memory.update_settings({'processing_paused': False})
            return json.dumps(generation(), ensure_ascii=False)
        agent = Agent(self.memory, model)
        result = agent.decide('a', '你好', 'paused-race', reply_mode='three_options')
        self.assertEqual(result['action'], 'handoff')
        self.assertEqual(self.memory.history('a'), [])
        self.assertIsNone(self.memory.cached('a', 'paused-race'))
