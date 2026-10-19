import asyncio
import importlib.util
import json
import threading

import httpx
import pytest

from test_jev_shadow import answer


def module():
    assert importlib.util.find_spec('london_product.query_router'), 'Active query classifier missing'
    from london_product import query_router
    return query_router


def make_router(tmp_path, handler=None, **config):
    m = module()
    from london_product.jev_shadow import ShadowConfig
    return m.QueryRouter(tmp_path, ShadowConfig(enabled=True, api_key='offline-only-key', **config),
                         transport=httpx.MockTransport(handler or (lambda req: httpx.Response(200, json=answer('saved_lookup')))))


def test_clear_local_query_and_explicit_modes_bypass_provider(tmp_path):
    router = make_router(tmp_path, lambda req: pytest.fail('classification should be bypassed'))
    async def run():
        for message in ['Show City rent', 'Compare City and Canary Wharf vacancy Q2 2026', '查询 City 租金']:
            route = await router.classify(message)
            assert route['mode'] == 'saved' and route['classifier'] == 'rules'
        for mode in ['saved', 'agent']:
            route = await router.classify('Explain market risks', mode)
            assert route['mode'] == mode and route['classifier'] == 'explicit'
    try: asyncio.run(run())
    finally: router.close(wait=True)


def test_jev_can_change_ambiguous_query_execution(tmp_path):
    router = make_router(tmp_path)
    try:
        route = asyncio.run(router.classify('Give me the London number'))
        assert route['classifier'] == 'jev' and route['mode'] == 'saved'
        assert route['intent'] == 'saved_lookup' and route['jev_attempted'] is True
        router.close(wait=True)
        row = json.loads((tmp_path/'routing'/'decisions.jsonl').read_text().splitlines()[0])
        assert row['decision']['mode'] == 'saved'
        assert 'Give me the London number' not in json.dumps(row)
        assert 'offline-only-key' not in json.dumps(router.status())
    finally: router.close(wait=True)


def test_analytical_intent_cannot_be_silently_downgraded(tmp_path):
    router = make_router(tmp_path)
    try:
        route = asyncio.run(router.classify('Explain risks in City rents'))
        assert route['classifier'] == 'jev' and route['mode'] == 'agent'
        assert route['policy_override'] == 'analysis_requested'
    finally: router.close(wait=True)


@pytest.mark.parametrize('label,notice', [('latest_information', 'LIVE_RESEARCH_UNAVAILABLE'),
                                        ('deep_research', 'DEEP_RESEARCH_WORKER_UNAVAILABLE')])
def test_capability_limits_are_explicit(tmp_path, label, notice):
    router = make_router(tmp_path, lambda req: httpx.Response(200, json=answer(label)))
    try:
        route = asyncio.run(router.classify('Investigate the newest occupier story'))
        assert notice in route['limitations']
        assert route['refresh_sources'] is False
    finally: router.close(wait=True)


@pytest.mark.parametrize('kind', ['http', 'low_confidence', 'invalid'])
def test_provider_problems_use_original_route(tmp_path, kind):
    value = answer('saved_lookup', confidence=.2 if kind == 'low_confidence' else .9)
    if kind == 'invalid': value['answers']['intent']['choice'] = 'execute_shell'
    router = make_router(tmp_path, lambda req: httpx.Response(503 if kind == 'http' else 200, json=value))
    try:
        route = asyncio.run(router.classify('Give me the London number'))
        assert route['mode'] == 'agent' and route['classifier'] == 'fallback'
        assert route['classification_status'] == {'http':'http_error','low_confidence':'low_confidence','invalid':'invalid_response'}[kind]
    finally: router.close(wait=True)


def test_missing_key_is_truthful_and_never_borrowed(tmp_path, monkeypatch):
    m = module()
    monkeypatch.delenv('LONDON_JEV_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'wrong-service-key')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'not-project-authorized')
    config = m.load_query_config(tmp_path/'missing.json')
    assert config.enabled and config.state == 'configuration_missing'
    router = m.QueryRouter(tmp_path, config)
    try:
        route = asyncio.run(router.classify('Investigate London'))
        assert route['classification_status'] == 'configuration_missing' and not route['jev_attempted']
    finally: router.close(wait=True)


def test_private_config_loaded_and_invalid_file_fails_closed(tmp_path, monkeypatch):
    m = module()
    config_path = tmp_path/'jev.json'
    monkeypatch.setenv('LONDON_JEV_API_KEY', 'old-key')
    config_path.write_text(json.dumps({'api_key':'project-local-key','enabled':True,'model':'jev-1.13.0'}))
    config = m.load_query_config(config_path)
    assert config.api_key == 'project-local-key' and config.state == 'ready'
    assert 'project-local-key' not in repr(config)
    config_path.write_text('{"api_key":"sensitive-value","enabled":"yes"}')
    assert m.load_query_config(config_path).state == 'invalid_configuration'


def test_timeout_capacity_and_budget_remain_bounded(tmp_path):
    entered = threading.Event()
    async def stall(req):
        entered.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json=answer())
    router = make_router(tmp_path, stall, timeout_seconds=.08, max_pending=1, max_calls=1)
    async def run():
        first = asyncio.create_task(router.classify('Investigate London'))
        while not entered.is_set(): await asyncio.sleep(.001)
        second = await router.classify('Investigate City')
        assert second['classification_status'] == 'capacity_exhausted'
        assert (await first)['classification_status'] == 'timeout'
        assert (await router.classify('Investigate West End'))['classification_status'] == 'budget_exhausted'
    try: asyncio.run(run())
    finally: router.close(wait=True)


def test_classifier_api_and_ask_use_actual_decision(tmp_path, monkeypatch):
    m = module()
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    router = make_router(tmp_path)
    monkeypatch.setattr(m, 'QueryRouter', lambda *a, **kw: router)
    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: pytest.fail('Answer model invoked for saved classification')
    with TestClient(app) as client:
        before = {table:len(app.state.market.store.all(table)) for table in ['facts','reports','jobs','events']}
        response = client.post('/api/market/routing/classify', json={'message':'Give me the London number'})
        assert response.status_code == 200 and response.json()['mode'] == 'saved'
        assert {table:len(app.state.market.store.all(table)) for table in before} == before
        status = client.get('/api/market/routing').json()
        assert status['controls_auto_execution'] is True
        response = client.post('/api/market/ask', json={'message':'Give me the London number','mode':'auto'})
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        assert events[-1]['type'] == 'done'
        assert events[-1]['metrics']['route']['classifier'] == 'jev'
        assert events[-1]['metrics']['model_requests'] == 0


def test_native_hook_and_tool_use_run_scoped_decision(tmp_path):
    module()
    from agno.run import RunContext
    from agno.run.agent import RunInput
    from agno.db.sqlite import SqliteDb
    from london_product.service import MarketService
    from london_product.store import Store
    from london_product.intelligence import query_agent
    service = MarketService(Store(tmp_path))
    service.query_router = make_router(tmp_path)
    try:
        agent = query_agent(service, SqliteDb(db_file=str(tmp_path/'native.sqlite3')))
        assert agent.pre_hooks
        context = RunContext(run_id='native-one', session_id='session', session_state={})
        asyncio.run(agent.pre_hooks[0](RunInput(input_content='Give me the London number'), context))
        decision = context.session_state['_market_query_route']
        assert decision['run_id'] == 'native-one' and decision['route']['classifier'] == 'jev'
        tool = next(t for t in agent.tools if getattr(t,'name',None) == 'search_market_evidence')
        pack = json.loads(tool.entrypoint(run_context=context, query='City rent'))
        assert pack['query_routing']['intent'] == 'saved_lookup'
        stale = RunContext(run_id='native-two', session_id='session', session_state=context.session_state)
        pack = json.loads(tool.entrypoint(run_context=stale, query='City rent'))
        assert 'query_routing' not in pack
    finally:
        service.query_router.close(wait=True)
        service.pool.shutdown(wait=True)


@pytest.mark.parametrize('field,value', [('timeout_seconds',10**309),('timeout_seconds','secret-value'),
                                        ('max_pending',True),('model',None),('api_key',['secret-value'])])
def test_malformed_configuration_never_breaks_status(tmp_path, field, value):
    m = module()
    config_path = tmp_path/'jev.json'
    config_path.write_text(json.dumps({'api_key':'fake',field:value}))
    router = m.QueryRouter(tmp_path, m.load_query_config(config_path))
    try:
        status = router.status()
        assert status['state'] == 'invalid_configuration'
        assert 'secret-value' not in json.dumps(status)
        assert asyncio.run(router.classify('Investigate London'))['classification_status'] == 'invalid_configuration'
    finally: router.close(wait=True)


def test_native_hook_reuses_only_server_scoped_context(tmp_path):
    m = module()
    from agno.run import RunContext
    from agno.run.agent import RunInput
    from agno.db.sqlite import SqliteDb
    from london_product.service import MarketService
    from london_product.store import Store
    from london_product.intelligence import query_agent
    service = MarketService(Store(tmp_path))
    service.query_router = make_router(tmp_path, lambda req: pytest.fail('Duplicate classifier request'))
    try:
        agent = query_agent(service, SqliteDb(db_file=str(tmp_path/'native.sqlite3')))
        context = RunContext(run_id='server-ask', session_id='s', session_state={})
        token = m.QUERY_ROUTE.set({'mode':'agent','classifier':'explicit','classification_status':'explicit'})
        try:
            asyncio.run(agent.pre_hooks[0](RunInput(input_content='Explain London'), context))
        finally:
            m.QUERY_ROUTE.reset(token)
        assert context.session_state['_market_query_route']['route']['classifier'] == 'explicit'
        assert service.query_router.status()['accepted'] == 0
    finally:
        service.query_router.close(wait=True); service.pool.shutdown(wait=True)


def test_active_call_cancellation_releases_capacity_and_log_error_is_nonfatal(tmp_path):
    entered = threading.Event()
    async def stall(req):
        entered.set(); await asyncio.sleep(.08)
        return httpx.Response(200, json=answer())
    (tmp_path/'routing').write_text('block receipt directory')
    router = make_router(tmp_path, stall, max_pending=1)
    async def run():
        task = asyncio.create_task(router.classify('Investigate London'))
        while not entered.is_set(): await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        for _ in range(100):
            if router.status()['in_flight'] == 0:break
            await asyncio.sleep(.005)
        assert router.status()['in_flight'] == 0
        route = await router.classify('Investigate City')
        assert route['classifier'] == 'jev'
    try: asyncio.run(run())
    finally: router.close(wait=True)
    assert router.status()['write_failures'] == 1


def test_slow_receipt_storage_does_not_block_classification(tmp_path, monkeypatch):
    router = make_router(tmp_path)
    entered = threading.Event(); release = threading.Event()
    assert hasattr(router, '_write_receipt'), 'Receipt writes must be isolated from the request loop'
    def slow_write(row):
        entered.set(); release.wait(2)
    monkeypatch.setattr(router, '_write_receipt', slow_write)
    try:
        route = asyncio.run(router.classify('Show City rent'))
        assert route['mode'] == 'saved'
        assert entered.wait(1) and not release.is_set()
    finally:
        release.set(); router.close(wait=True)


def test_disable_flag_restores_original_auto_rules(tmp_path):
    m = module()
    from london_product.jev_shadow import ShadowConfig
    from london_product.routing import route_question
    router = m.QueryRouter(tmp_path, ShadowConfig(enabled=False))
    try:
        for query in ['Explain City rent', 'Prepare a City report', 'Show City rent']:
            route = asyncio.run(router.classify(query))
            assert route['mode'] == route_question(query)['mode']
            assert route['classification_status'] == 'disabled' and not route['jev_attempted']
    finally: router.close(wait=True)


def test_native_http_run_executes_classifier_hook_offline(tmp_path, monkeypatch):
    m = module()
    from fastapi.testclient import TestClient
    from agno.models.openai import OpenAIChat
    from agno.models.response import ModelResponse
    from agno.models.metrics import MessageMetrics
    from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall, ChoiceDeltaToolCallFunction
    from london_product.runtime import create_app
    router = make_router(tmp_path)
    monkeypatch.setattr(m, 'QueryRouter', lambda *a, **kw: router)
    async def fake_stream(self, *args, **kwargs):
        messages = kwargs.get('messages', args[0] if args else [])
        if not any(message.role == 'tool' for message in messages):
            yield ModelResponse(tool_calls=[ChoiceDeltaToolCall(index=0,id='offline-tool',type='function',
                function=ChoiceDeltaToolCallFunction(name='search_market_evidence',arguments=json.dumps({'query':'City rent'})))])
        else:
            yield ModelResponse(content='No verified evidence is available; no current market conclusion is asserted.')
        yield ModelResponse(response_usage=MessageMetrics(input_tokens=10, output_tokens=10))
    monkeypatch.setattr(OpenAIChat, 'ainvoke_stream', fake_stream)
    app = create_app(tmp_path, seed=False, scheduler=False)
    with TestClient(app) as client:
        response = client.post('/agents/london-market-agent/runs', data={
            'message':'Give me the London number','stream':'true','stream_events':'true'})
        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        assert any(e.get('event') == 'PreHookCompleted' for e in events)
        assert any(e.get('event') == 'RunCompleted' for e in events)
        tools = [e['tool'] for e in events if e.get('event') == 'ToolCallCompleted']
        assert tools
        pack = json.loads(tools[0]['result'])
        assert pack['query_routing']['classifier'] == 'jev'
        assert router.status()['accepted'] == 1


def test_receipt_thread_start_failure_does_not_fail_request_or_close(tmp_path, monkeypatch):
    router = make_router(tmp_path)
    original_start = threading.Thread.start
    def fail_writer(thread):
        if thread.name == 'jev-routing-receipts':raise RuntimeError('thread resources unavailable')
        return original_start(thread)
    monkeypatch.setattr(threading.Thread, 'start', fail_writer)
    try:
        route = asyncio.run(router.classify('Show City rent'))
        assert route['mode'] == 'saved' and router.status()['write_failures'] == 1
        assert router.status()['receipt_dropped'] == 1
    finally: router.close(wait=True)
