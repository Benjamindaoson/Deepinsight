"""Offline regressions for the recorded Native Agent failure; no provider calls."""
import json
import sqlite3
import pytest
from pathlib import Path
from types import SimpleNamespace

from agno.models.message import Message
from agno.run import RunContext
from fastapi.testclient import TestClient
from london_product.intelligence import query_agent, query_model
from london_product.service import MarketService
from london_product.store import Store


def saved_service(tmp_path):
    original = Path(__file__).parents[1] / 'data/product/market.sqlite3'
    store = Store(tmp_path)
    with sqlite3.connect(original.as_uri() + '?mode=ro', uri=True) as db:
        for table in ['sources', 'documents', 'facts', 'events']:
            for identity, payload in db.execute(f'SELECT identity,payload FROM {table}'):
                row = json.loads(payload)
                if table == 'facts':
                    # The fixture models a market with no human-approved facts.
                    # Live review decisions belong to the running product, not
                    # to an offline regression, so pin the review state here.
                    row['status'] = 'pending_review'
                    row['human_review_status'] = 'pending_review'
                    row.pop('reviewed_by', None)
                    row.pop('reviewed_at', None)
                    row.pop('review_note', None)
                store.put(table, identity, row)
    return MarketService(store)


def test_real_evidence_search_is_bounded_and_deduplicated_per_run(tmp_path):
    service = saved_service(tmp_path)
    agent = query_agent(service, None)
    loader = next(t for t in agent.tools if t.name == 'load_market_skills')
    search = next(t for t in agent.tools if t.name == 'search_market_evidence')
    context = RunContext(run_id='offline-a', session_id='offline', session_state={})
    loader.entrypoint(run_context=context, skill_names=['market-intelligence'])
    import inspect
    initial_context = {'run_context': context} if 'run_context' in inspect.signature(search.entrypoint).parameters else {}
    first = search.entrypoint(query='London office market recent quarter changes risks opportunities 2026', **initial_context)
    assert len(first.encode()) <= 10000
    second = search.entrypoint(query='London office market Q2 2026 trends investment demand supply pipeline risks opportunities outlook', run_context=context)
    assert len(first.encode()) <= 10000
    assert len(second.encode()) <= 10000
    a, b = json.loads(first), json.loads(second)
    assert a['facts']
    assert not ({f['id'] for f in a['facts']} & {f['id'] for f in b['facts']})
    assert not ({e['id'] for e in a['events']} & {e['id'] for e in b['events']})
    for result in [a, b]:
        for fact in result['facts']:
            from london_product.normalization import current_fact
            saved = current_fact(service.store.get('facts', fact['id']))
            for key in ['value', 'unit', 'definition', 'status', 'period', 'evidence']:
                assert fact[key] == saved.get(key)
            assert result['documents'][fact['document_id']]['url'] == service.store.get('documents', fact['document_id'])['url']
        for event in result['events']:
            from london_product.analysis_guard import event_context
            assert event['transaction_context'] == event_context(service.store.get('events', event['id']), service.store)
    # Same query is not retrieved again, but another run starts cleanly.
    repeat = json.loads(search.entrypoint(query='London office market recent quarter changes risks opportunities 2026', run_context=context))
    assert repeat['facts'] == [] and repeat['events'] == []
    assert repeat['duplicate_query'] is True
    fresh = RunContext(run_id='offline-b', session_id='offline', session_state=context.session_state)
    loader.entrypoint(run_context=fresh, skill_names=['market-intelligence'])
    assert json.loads(search.entrypoint(query='London office market recent quarter changes risks opportunities 2026', run_context=fresh))['facts'] == a['facts']
    # Conservative byte estimate and limits stay unchanged; two compact tool results fit.
    model = query_model()
    messages = [Message(role='user', content='London changes risks opportunities?')]
    for index, result in enumerate([first, second]):
        model._reserve((), dict(messages=messages, run_response=SimpleNamespace(run_id='replay')))
        model.budget.after([1893, 8534][index], [60, 66][index])
        messages.append(Message(role='tool', tool_name='search_market_evidence', content=result))
    model._reserve((), dict(messages=messages, run_response=SimpleNamespace(run_id='replay')))
    assert model.budget.requests == 3


def test_first_search_required_but_followup_not_forced_to_repeat():
    model = query_model()
    args = dict(messages=[], tools=[{'type': 'function'}], tool_choice='required', run_response=SimpleNamespace(run_id='choice'))
    model._reserve((), args)
    assert args['tool_choice'] == {'type': 'function', 'function': {'name': 'search_market_evidence'}}
    model.budget.after(10, 2)
    args['messages'] = [Message(role='tool', tool_name='search_market_evidence', tool_call_error=False, content='{}')]
    model._reserve((), args)
    assert args['tool_choice'] == 'auto'
    model.budget.after(10, 2)
    args['tool_choice'] = 'none'
    model._reserve((), args)
    assert args['tool_choice'] == 'none'  # Native tool limit remains authoritative.


def test_budget_error_reaches_sse_and_job_without_raw_provider_details(tmp_path):
    from london_product.runtime import create_app
    app = create_app(tmp_path, seed=False, scheduler=False)
    class Agent:
        model = SimpleNamespace(budget_for=lambda _: SimpleNamespace(record=lambda: dict(requests=2, input_tokens=10427, output_tokens=126)))
        async def arun(self, *args, **kwargs):
            yield SimpleNamespace(event='RunError', content='TOKEN_BUDGET', run_id='offline-error')
    app.state.market.agent_factory = Agent
    with TestClient(app) as client:
        response = client.post('/api/market/ask', json={'message': 'London?', 'mode': 'agent'})
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert events[-1]['type'] == 'error'
    assert events[-1]['code'] == 'TOKEN_BUDGET_EXCEEDED'
    assert 'budget' in events[-1]['message'].lower()
    assert 'narrower question' in events[-1]['message'].lower()
    assert not any(e['type'] in ['done', 'token'] for e in events)
    job = app.state.market.store.all('jobs')[0]
    assert job['error_code'] == 'TOKEN_BUDGET_EXCEEDED'
    assert job['metrics']['requests'] == 2


def test_context_changes_do_not_raise_budget_or_suppress_excess():
    from london_product.intelligence import Budget
    budget = Budget(max_requests=3)
    for _ in range(3):
        budget.before(100, 1800)
        budget.after(10, 2)
    with pytest.raises(ValueError, match='REQUEST_OR_TIME_BUDGET'):
        budget.before(1, 1)
    for input_used, output_used in [(59999, 0), (0, 7999)]:
        budget = Budget(max_requests=3, input_tokens=input_used, output_tokens=output_used)
        with pytest.raises(ValueError, match='TOKEN_BUDGET'):
            budget.before(2, 2)


def test_oversized_qualifiers_are_omitted_whole_not_truncated(tmp_path):
    store = Store(tmp_path)
    store.put('sources', 's', dict(id='s', allow_llm=True))
    quote = 'pre-let ' + ('x' * 15000) + ' or under offer'
    doc = store.put('documents', 'd', dict(id='d', source_id='s', url='https://example.org/large', segments=[dict(text=quote, locator='html:main')]))
    store.put('facts', 'f', dict(id='f', source_id='s', document_id=doc['id'], value='80', metric='prelet_share', unit='percent', status='needs_review', evidence=dict(quote=quote)))
    store.put('events', 'e', dict(id='e', source_id='s', document_id=doc['id'], status='pending_review', evidence=dict(quote=quote)))
    agent = query_agent(MarketService(store), None)
    loader = next(t for t in agent.tools if t.name == 'load_market_skills')
    tool = next(t for t in agent.tools if t.name == 'search_market_evidence')
    context = RunContext(run_id='large', session_id='offline', session_state={})
    loader.entrypoint(run_context=context, skill_names=['market-intelligence'])
    result = tool.entrypoint(run_context=context, query='pre-let')
    assert len(result.encode()) <= 10000
    data = json.loads(result)
    assert data['facts'] == [] and data['events'] == []
    assert data['coverage']['saved_fact_records'] == 1
