"""The production LangGraph workflow, shared by HTTP and direct callers."""
import time
import uuid
from typing import TypedDict

from .core import RISK
from .skills import instructions


class ConversationState(TypedDict, total=False):
    contact_id: str
    message: str
    message_id: str | None
    owner: str
    skill: str | None
    authorized: bool
    sensitive: bool
    snapshot: dict
    context: dict
    analysis: dict
    intent: str
    selected_skills: list[str]
    trace: list[dict]
    result: dict


def build_graph(agent):
    from langgraph.graph import StateGraph, START, END
    graph = StateGraph(ConversationState)

    def traced(name, function):
        def execute(state):
            started = time.perf_counter()
            update = function(state)
            update['trace'] = state.get('trace', []) + [{'node': name, 'duration_ms': round((time.perf_counter() - started) * 1000, 2)}]
            return update
        return execute

    def receive(state):
        if not isinstance(state.get('message'), str) or not 1 <= len(state['message']) <= 4000:
            raise ValueError('invalid message')
        return {'owner': state.get('owner') or uuid.uuid4().hex}

    def identify(state):
        snapshot = agent.prepare(state['contact_id'], state.get('message_id'), state['owner'])
        if 'result' in snapshot:
            return {'result': snapshot['result'], 'authorized': False}
        return {'snapshot': snapshot, 'authorized': True}

    def retrieve(state):
        snapshot = state['snapshot']
        recalled = []
        if agent.semantic:
            try:
                recalled = agent.semantic.search(state['contact_id'], state['message'])
            except Exception:
                recalled = []
        return {'context': {'facts': snapshot['facts'], 'history': snapshot['history'], 'recalled': recalled}}

    def emotion(state):
        text = state['message']
        cues = [word for word in ('开心', '难过', '累', '烦', '谢谢', '生气', '担心', '哈哈') if word in text]
        return {'analysis': {'expression_cues': cues, 'uncertain': True,
                             'note': '表达线索仅供参考，不能据此判断性格或感情状态'},
                'sensitive': any(term in text for term in RISK)}

    def intent(state):
        return {'intent': 'question' if any(mark in state['message'] for mark in ('?', '？', '吗', '怎么')) else 'sharing'}

    def route_skill(state):
        requested = state.get('skill')
        selected = requested or 'romance-reply'
        try:
            instructions(selected, agent.memory.settings())
        except ValueError:
            return {'result': {'action': 'handoff', 'reason': '所选技能不可用', 'record_message': False}}
        return {'selected_skills': [selected, 'relationship-memory', 'boundary-guardian']}

    def generate(state):
        snapshot = dict(state['snapshot'])
        snapshot['task_instructions'] = instructions(state['selected_skills'][0], agent.memory.settings())
        recalled = {item['memory'] for item in state.get('context', {}).get('recalled', [])}
        weights = {item['key']: item['weight'] for item in agent.memory.fact_details(state['contact_id'])}
        ranked = sorted(snapshot['facts'].items(), key=lambda item: (
            not item[0].startswith('边界'), item[0] + ' ' + item[1] not in recalled, -weights.get(item[0], 1)))
        snapshot['facts'] = dict(ranked[:30])
        return {'result': agent._decide(state['message'], snapshot)}

    def review(state):
        result = dict(state['result'])
        if result.get('action') == 'draft':
            result['requires_confirmation'] = True
            result['analysis'] = result.get('analysis', state['analysis'])
            result['skills'] = state['selected_skills']
        return {'result': result}

    def handoff(state):
        return {'result': {'action': 'handoff', 'reason': '重要或敏感话题，请本人处理',
                           'record_message': False, 'audit_decision': 'handoff:sensitive'}}

    def persist(state):
        snapshot = state['snapshot']
        result = agent.memory.finish(state['contact_id'], state.get('message_id'), state['owner'],
                                     snapshot['revision'], state['message'], dict(state['result']))
        if result.get('action') == 'draft':
            agent.memory.offer_candidates(state['contact_id'], state['message'], snapshot['revision'])
        agent.memory.save_run(state['owner'], state['contact_id'], result['action'], state.get('trace', []) + [{'node': 'memory_update'}])
        return {'result': result}

    nodes = [('message_receive', receive), ('contact_identify', identify),
             ('memory_retrieve', retrieve), ('emotion_analysis', emotion),
             ('intent_analysis', intent), ('skill_route', route_skill),
             ('reply_generate', generate), ('reply_review', review),
             ('human_handoff', handoff), ('memory_update', persist)]
    for name, function in nodes:
        graph.add_node(name, traced(name, function))
    graph.add_edge(START, 'message_receive')
    graph.add_edge('message_receive', 'contact_identify')
    graph.add_conditional_edges('contact_identify', lambda state: 'memory_retrieve' if state['authorized'] else END)
    graph.add_edge('memory_retrieve', 'emotion_analysis')
    graph.add_conditional_edges('emotion_analysis', lambda state: 'human_handoff' if state['sensitive'] else 'intent_analysis')
    graph.add_edge('intent_analysis', 'skill_route')
    graph.add_conditional_edges('skill_route', lambda state: 'memory_update' if 'result' in state else 'reply_generate')
    graph.add_edge('reply_generate', 'reply_review')
    graph.add_edge('reply_review', 'memory_update')
    graph.add_edge('human_handoff', 'memory_update')
    graph.add_edge('memory_update', END)
    return graph.compile()
