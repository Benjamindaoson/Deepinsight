"""Offline / Mock checks only. No requests to the model provider."""
import json
from types import SimpleNamespace
import pytest
from agno.models.message import Message
from london_product.intelligence import query_model


def test_payload_estimate_counts_tool_schemas_and_records_rejections():
    model = query_model()
    args = dict(messages=[Message(role='system', content='Evidence only'), Message(role='user', content='伦敦市场')],
                tools=[dict(type='function', function=dict(name='search_market_evidence', description='data', parameters={'type':'object'}))],
                run_response=SimpleNamespace(run_id='offline-estimate'))
    model._reserve((), args)
    call = model.budget.record()['calls'][0]
    assert call['estimate']['components']['tools'] > 0
    assert call['estimate']['method'] == 'calibrated-character-envelope-v1'
    assert call['estimate']['calibration_samples'] == 4
    assert call['estimate']['payload_sha256']
    model.budget.after(40, 5)
    args['messages'] = [Message(role='user', content='x' * 200000)]
    with pytest.raises(ValueError, match='TOKEN_BUDGET'):
        model._reserve((), args)
    record = model.budget.record()
    assert record['requests'] == 1
    assert record['input_tokens'] == 40
    assert record['decisions'][-1]['allowed'] is False


def test_third_request_forces_final_answer_and_single_request_cap():
    model = query_model()
    args = dict(messages=[Message(role='tool', tool_name='search_market_evidence', content='{}')],
                tools=[{'type':'function'}], run_response=SimpleNamespace(run_id='third'))
    for _ in range(2):
        model._reserve((), args)
        model.budget.after(100, 10)
    model._reserve((), args)
    assert args['tool_choice'] == 'none'
    with pytest.raises(ValueError, match='PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'):
        model.budget.after(100, 1801)
    assert model.budget.record()['output_tokens'] == 1821


def test_wire_compression_preserves_raw_messages_and_fact_qualifiers():
    model = query_model()
    pack = dict(facts=[dict(id=str(i), value='95', unit='GBP/sqft unknown annual basis', status='needs_review',
                period='2026Q2', definition='prime rent', document_id='d', evidence={'quote':'£95 per sq ft','page':3}) for i in range(60)],
                events=[], documents={'d':{'url':'https://example.org/report'}}, review_notice='Unapproved')
    original = Message(role='tool', tool_name='search_market_evidence', content=json.dumps(pack))
    args = dict(messages=[original], run_response=SimpleNamespace(run_id='compression'))
    model._reserve((), args);model.budget.after(53000, 1)
    model._reserve((), args)
    assert original.content == json.dumps(pack)
    result = json.loads(args['messages'][0].content)
    assert len(result['facts']) < 60
    assert result['facts'][0] == pack['facts'][0]
    assert model.budget.record()['decisions'][-1]['compression']


@pytest.mark.parametrize('native,expected', [
    ('TOKEN_BUDGET','TOKEN_BUDGET_EXCEEDED'),
    ('MODEL_TIMEOUT','MODEL_TIMEOUT'),('TOOL_ERROR','TOOL_ERROR'),
    ('FINAL_ANSWER_MISSING','FINAL_ANSWER_MISSING'),
    ('insufficient_user_quota','PROVIDER_QUOTA_EXHAUSTED'),
    ('MODEL_OUTPUT_TRUNCATED','MODEL_OUTPUT_TRUNCATED'),
    ('secret-provider-error','PROVIDER_ERROR')])
def test_error_stage_and_final_answer_state(tmp_path, native, expected):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app = create_app(tmp_path, seed=False, scheduler=False)
    class Agent:
        model = SimpleNamespace(budget_for=lambda _: SimpleNamespace(record=lambda: dict(requests=1, input_tokens=10, output_tokens=1)))
        async def arun(self, *args, **kwargs):
            yield SimpleNamespace(event='RunError', content=native, run_id='mock-error')
    app.state.market.agent_factory = Agent
    with TestClient(app) as client:
        response = client.post('/api/market/ask',json=dict(message='London?',mode='agent'))
    result = [json.loads(x[6:]) for x in response.text.splitlines() if x.startswith('data: ')][-1]
    assert result['code'] == expected
    assert result['final_answer_generated'] is False
    assert result['stage']
    assert 'secret-provider-error' not in result['message']


def test_last_provider_tool_request_never_reaches_tool_execution(monkeypatch):
    import asyncio
    from agno.models.openai import OpenAIChat
    from agno.models.response import ModelResponse
    from agno.models.metrics import MessageMetrics
    model = query_model()
    args = dict(messages=[], run_response=SimpleNamespace(run_id='mock-last'))
    for _ in range(2):
        model._reserve((), args); model.budget.after(10, 1)
    async def fake_stream(self, *a, **kw):
        assert kw['tool_choice'] == 'none'
        yield ModelResponse(tool_calls=[{'id':'mock','type':'function','function':{'name':'search_market_evidence','arguments':'{}'}}])
        yield ModelResponse(response_usage=MessageMetrics(input_tokens=12, output_tokens=3))
    monkeypatch.setattr(OpenAIChat,'ainvoke_stream',fake_stream)
    received = []
    async def run():
        async for part in model.ainvoke_stream(**args):received.extend(part.tool_calls)
    with pytest.raises(ValueError, match='FINAL_ANSWER_MISSING'):asyncio.run(run())
    assert received == []
    assert model.budget.record()['requests'] == 3
    assert model.budget.record()['input_tokens'] == 32


def test_missing_usage_is_not_reported_as_actual_estimate():
    from london_product.intelligence import QuestionBudget
    b = QuestionBudget(max_requests=3)
    b.before(5000,1800)
    b.failed(TimeoutError())
    record = b.record()
    assert record['input_tokens'] is None
    assert record['known_input_tokens'] == 0
    assert record['calls'][0]['estimated_input'] == 5000
    with pytest.raises(ValueError,match='PROVIDER_USAGE_MISSING'):b.before(100,100)


def test_calibration_samples_reproduce_from_real_records_without_network():
    import hashlib, math
    from pathlib import Path
    from london_product.qa_context import calibration, character_units
    model = query_model(); config = calibration();root=Path(__file__).parents[2]
    for sample in config['samples']:
        path=root/sample['evidence_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sample['evidence_sha256']
        run=json.loads(path.read_text(encoding='utf-8'));i=sample['message_index']
        payload=model._format_all_messages([Message(**m) for m in run['messages'][:i]],False)
        assert character_units(payload)==sample['message_character_units']
        assert run['messages'][i]['metrics']['input_tokens']==sample['provider_input_tokens']
        assert math.ceil(character_units(payload)*config['multiplier'])>=sample['provider_input_tokens']


def test_evidence_pack_is_topic_limited_and_preserves_statuses(tmp_path):
    from london_product.qa_context import evidence_pack
    from test_qa_context_budget import saved_service
    service = saved_service(tmp_path)
    memo={'facts':[],'events':[]}
    narrow=evidence_pack(service,'City rent',memo)
    broad=evidence_pack(service,'London changes risks opportunities',memo)
    assert set(narrow['topics'])=={'rent'}
    assert len(narrow['facts'])<=3
    assert len(broad['facts'])<=8
    assert broad['notice_code']=='NO_VERIFIED_EVIDENCE'
    for f in broad['facts']:
        from london_product.normalization import current_fact
        original=current_fact(service.store.get('facts',f['id']))
        assert f['status']==original['status'] and f['candidate_only']
        assert len(f['evidence']['quote'])<=700
        assert 'published_at' in broad['documents'][f['document_id']]
    service.pool.shutdown(wait=False)


def test_period_ranking_does_not_put_q1_label_ahead_of_q2():
    from london_product.qa_context import period_order
    assert period_order({'period':'Q1 2026'}) < period_order({'period':'2026Q2'})
