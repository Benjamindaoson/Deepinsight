import asyncio
import importlib.util
import json
import subprocess
import sys
import threading
import time

import httpx
import pytest


LABELS = ('saved_lookup', 'market_comparison', 'latest_information',
          'focused_analysis', 'full_report', 'deep_research')


def module():
    assert importlib.util.find_spec('london_product.jev_shadow'), 'Jev shadow observer missing'
    from london_product import jev_shadow
    return jev_shadow


def answer(label='full_report', confidence=.9):
    return {'model': 'jev-1.13.0', 'usage': {'input_tokens': 200, 'output_tokens': 10},
            'answers': {
                'intent': {'type': 'choice', 'choice': label, 'confidence': confidence,
                           'probabilities': {k: float(k == label) for k in LABELS}},
                'freshness': {'type': 'noul', 'noul': .8},
                'reasoning': {'type': 'noul', 'noul': .7},
                'complexity': {'type': 'score', 'score': 2., 'confidence': .8,
                               'legend': {'0': 'lookup', '1': 'compare', '2': 'analysis', '3': 'research'},
                               'probabilities': {'0': 0., '1': 0., '2': 1., '3': 0.}}}}


def observer(tmp_path, handler, **kwargs):
    m = module()
    config = m.ShadowConfig(enabled=True, api_key='dedicated-test-secret', **kwargs)
    return m.JevShadowObserver(tmp_path, config, transport=httpx.MockTransport(handler))


def submit(obs, query='Private question', identity='ask-1'):
    return obs.submit(query, {'mode': 'saved', 'reason': 'explicit_selection'}, 'saved', identity)


def receipts(tmp_path):
    path = tmp_path/'routing-shadow'/'observations.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def test_disabled_and_missing_key_never_call_provider(tmp_path, monkeypatch):
    m = module()
    monkeypatch.delenv('LONDON_JEV_SHADOW_ENABLED', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-inherit')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'also-not-inherited')
    monkeypatch.delenv('LONDON_JEV_API_KEY', raising=False)
    for config, state in [(m.ShadowConfig.from_env(), 'disabled'),
                          (m.ShadowConfig(enabled=True), 'configuration_missing')]:
        obs = m.JevShadowObserver(tmp_path, config, transport=httpx.MockTransport(
            lambda req: pytest.fail('unexpected provider request')))
        assert submit(obs) is False
        assert obs.status()['state'] == state
        obs.close()
    assert not (tmp_path/'routing-shadow').exists()


def test_official_contract_private_receipt_and_disagreement(tmp_path):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=answer())
    obs = observer(tmp_path, handler)
    query = 'Private client: show City rent'
    actual = {'mode': 'saved', 'reason': 'explicit_selection'}
    assert obs.submit(query, actual, 'saved', 'ask-1')
    obs.close(wait=True)
    assert actual == {'mode': 'saved', 'reason': 'explicit_selection'}
    assert str(seen[0].url) == 'https://api.typesafe.ai/v1/systemone'
    assert seen[0].headers['authorization'] == 'Bearer dedicated-test-secret'
    payload = json.loads(seen[0].content)
    assert payload['state'] == {'question': query}
    assert tuple(payload['questions']['intent']['criteria']) == LABELS
    assert payload['questions']['complexity']['type'] == 'score'
    row, = receipts(tmp_path)
    assert row['status'] == 'ok' and row['submission_id'] == 'ask-1'
    assert row['suggestion']['intent'] == 'full_report' and row['coarse_disagreement'] is True
    assert row['actual_route'] == actual and row['rule_route']['mode'] == 'saved'
    assert row['model_returned'] == 'jev-1.13.0'
    assert row['usage']['input_tokens'] == 200
    text = json.dumps(row)
    assert query not in text and 'dedicated-test-secret' not in text
    assert obs.status()['in_flight'] == 0


@pytest.mark.parametrize('mutation', [
    lambda r: r['answers']['intent'].update(choice='delete_database'),
    lambda r: r['answers']['intent']['probabilities'].pop('saved_lookup'),
    lambda r: r['answers']['intent']['probabilities'].update(saved_lookup=float('nan')),
    lambda r: r['answers']['intent'].update(confidence=True),
    lambda r: r['answers']['intent'].update(confidence=10**309),
    lambda r: r['answers']['freshness'].update(noul=1.1),
    lambda r: r['answers']['complexity'].update(score=4),
    lambda r: r['answers'].pop('reasoning'),
    lambda r: r.update(usage={'input_tokens': -1}),
])
def test_invalid_provider_output_never_counts_as_success(tmp_path, mutation):
    value = answer(); mutation(value)
    # JSON NaN is intentionally delivered as nonstandard provider output.
    obs = observer(tmp_path, lambda req: httpx.Response(200, content=json.dumps(value)))
    assert submit(obs)
    obs.close(wait=True)
    row, = receipts(tmp_path)
    assert row['status'] == 'invalid_response'
    assert 'suggestion' not in row


@pytest.mark.parametrize('status', [401, 429, 500])
def test_http_failures_do_not_retry_or_log_bodies(tmp_path, status):
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(status, text='Private question dedicated-test-secret')
    obs = observer(tmp_path, handler)
    assert submit(obs)
    obs.close(wait=True)
    row, = receipts(tmp_path)
    assert row['status'] == 'http_error' and row['http_status'] == status
    assert len(calls) == 1
    assert 'dedicated-test-secret' not in json.dumps(row)


def test_hard_deadline_capacity_and_nonblocking_admission(tmp_path):
    entered = threading.Event()
    async def handler(req):
        entered.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json=answer())
    obs = observer(tmp_path, handler, timeout_seconds=.08, max_pending=1)
    started = time.perf_counter()
    assert submit(obs)
    assert time.perf_counter()-started < .1
    assert entered.wait(1)
    assert not submit(obs, identity='ask-2')
    obs.close(wait=True)
    assert receipts(tmp_path)[0]['status'] == 'timeout'
    assert obs.status()['dropped_capacity'] == 1
    assert obs.status()['in_flight'] == 0
    assert not submit(obs, identity='ask-3')


def test_log_failure_is_counted_and_releases_slot(tmp_path):
    (tmp_path/'routing-shadow').write_text('cannot create directory here')
    obs = observer(tmp_path, lambda req: httpx.Response(200, json=answer()))
    assert submit(obs)
    obs.close(wait=True)
    assert obs.status()['write_failures'] == 1
    assert obs.status()['in_flight'] == 0


def test_low_confidence_is_only_a_diagnostic(tmp_path):
    obs = observer(tmp_path, lambda req: httpx.Response(200, json=answer(confidence=.2)))
    assert submit(obs)
    obs.close(wait=True)
    row, = receipts(tmp_path)
    assert row['status'] == 'ok' and row['suggestion']['low_confidence'] is True
    assert row['actual_route']['mode'] == 'saved'


def test_summary_requires_labels_for_accuracy(tmp_path):
    obs = observer(tmp_path, lambda req: httpx.Response(200, json=answer()))
    assert submit(obs, query='Show City rent')
    obs.close(wait=True)
    from london_product.shadow_metrics import summarize
    rows = receipts(tmp_path)
    result = summarize(rows)
    assert result['accuracy'] is None and result['labeled_count'] == 0
    assert result['coarse_disagreements'] == 1
    assert result['latency_ms']['p95'] == rows[0]['elapsed_ms']
    assert summarize(rows, {'ask-1': 'full_report'})['accuracy'] == 1.
    assert summarize(rows, {'ask-1': 'saved_lookup'})['accuracy'] == 0.


def test_api_keeps_saved_route_while_shadow_disagrees(tmp_path, monkeypatch):
    m = module()
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    obs = observer(tmp_path, lambda req: httpx.Response(200, json=answer()))
    monkeypatch.setattr(m, 'JevShadowObserver', lambda *a, **k: obs)
    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: pytest.fail('answer model invoked')
    with TestClient(app) as client:
        for mode in ['saved', 'auto']:
            response = client.post('/api/market/ask', json={'message': 'Show City rent', 'mode': mode})
            assert response.status_code == 200
            events = [json.loads(s[6:]) for s in response.text.splitlines() if s.startswith('data: ')]
            done = next(e for e in events if e['type'] == 'done')
            assert done['metrics']['route']['mode'] == 'saved'
            assert done['metrics']['model_requests'] == 0
        assert client.get('/api/market/routing/shadow').json()['controls_execution'] is False
        client.post('/api/market/ask', json={'message': 'rent', 'parent_report_id': 'missing'})
    obs.close(wait=True)
    rows = receipts(tmp_path)
    assert len(rows) == 2 and all(r['actual_route']['mode'] == 'saved' for r in rows)


def test_api_does_not_wait_for_provider_and_closes_pending_work(tmp_path, monkeypatch):
    m = module()
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    release = threading.Event()
    entered = threading.Event()
    async def handler(req):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(.01)
        return httpx.Response(200, json=answer())
    obs = observer(tmp_path, handler)
    monkeypatch.setattr(m, 'JevShadowObserver', lambda *a, **k: obs)
    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: pytest.fail('answer model invoked')
    try:
        with TestClient(app) as client:
            response = client.post('/api/market/ask', json={'message': 'City rent', 'mode': 'saved'})
            assert response.status_code == 200 and '"type": "done"' in response.text
            assert entered.wait(1) and not release.is_set()
            assert obs.status()['in_flight'] == 1
            assert client.get('/api/market/routing/shadow').status_code == 200
    finally:
        release.set()
        obs.close(wait=True)


def test_queue_cancel_and_call_budget_are_bounded(tmp_path):
    release = threading.Event(); entered = threading.Event()
    async def handler(req):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(.01)
        return httpx.Response(200, json=answer())
    obs = observer(tmp_path, handler, max_calls=2)
    try:
        assert submit(obs, identity='ask-1') and entered.wait(1)
        assert submit(obs, identity='ask-2')
        assert not submit(obs, identity='ask-3')
        obs.close()
    finally:
        release.set()
        obs.close(wait=True)
    assert obs.status()['cancelled'] == 1
    assert obs.status()['dropped_budget'] == 1
    assert len(receipts(tmp_path)) == 1


@pytest.mark.parametrize('variable,value', [
    ('LONDON_JEV_TIMEOUT_SECONDS', 'nan'), ('LONDON_JEV_TIMEOUT_SECONDS', 'bad'),
    ('LONDON_JEV_MODEL', 'https://other.example'), ('LONDON_JEV_MAX_PENDING', '-1'),
])
def test_bad_configuration_fails_closed(tmp_path, monkeypatch, variable, value):
    m = module()
    monkeypatch.setenv('LONDON_JEV_SHADOW_ENABLED', '1')
    monkeypatch.setenv('LONDON_JEV_API_KEY', 'dedicated-test-secret')
    monkeypatch.setenv(variable, value)
    obs = m.JevShadowObserver(tmp_path)
    assert obs.status()['state'] == 'invalid_configuration'
    assert submit(obs) is False
    assert 'dedicated-test-secret' not in repr(obs.config)
    obs.close()


def test_summary_reports_failures_quantiles_and_corrupt_lines(tmp_path):
    module()
    from london_product.shadow_metrics import read_receipts, summarize
    rows = [dict(status='ok', submission_id=str(i), elapsed_ms=i,
                 suggestion={'intent': 'saved_lookup', 'low_confidence': False}) for i in range(1, 21)]
    path = tmp_path/'receipts.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\nnot json\n{}\n'+
                    json.dumps({'status': 'timeout', 'elapsed_ms': 10**309})+'\n'+
                    json.dumps({'status': 'timeout', 'elapsed_ms': 80})+'\n', encoding='utf-8')
    valid, invalid = read_receipts(path)
    assert invalid == 3
    result = summarize(valid)
    assert result['latency_ms'] == {'p50': 10, 'p95': 19}
    assert result['statuses']['timeout'] == 1 and result['observations'] == 21
    with pytest.raises(ValueError):
        summarize(valid, {'1': 'invented_label'})


def test_production_wall_deadline_kills_stuck_child(tmp_path, monkeypatch):
    m = module()
    real_popen = subprocess.Popen
    children = []
    def blocked_child(*args, **kwargs):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(30)'], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(m.subprocess, 'Popen', blocked_child)
    obs = m.JevShadowObserver(tmp_path, m.ShadowConfig(enabled=True, api_key='fake', timeout_seconds=.1))
    started = time.perf_counter()
    assert submit(obs)
    obs.close(wait=True)
    assert time.perf_counter()-started < 1.5
    assert receipts(tmp_path)[0]['status'] == 'timeout'
    assert children[0].poll() is not None


@pytest.mark.parametrize('mode', ['agent', 'auto'])
@pytest.mark.parametrize('provider_status', [200, 503])
def test_agent_route_and_publication_guard_survive_shadow(tmp_path, monkeypatch, mode, provider_status):
    m = module()
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    obs = observer(tmp_path, lambda req: httpx.Response(provider_status, json=answer('saved_lookup')))
    monkeypatch.setattr(m, 'JevShadowObserver', lambda *a, **k: obs)
    app = create_app(tmp_path, seed=False, scheduler=False)
    calls = []
    class OfflineAgent:
        model = SimpleNamespace(budget_for=lambda _: SimpleNamespace(record=lambda: dict(requests=0)))
        async def arun(self, *args, **kwargs):
            calls.append(args)
            yield SimpleNamespace(event='ToolCallCompleted', run_id='offline', tool=SimpleNamespace(
                tool_name='load_market_skills', tool_call_error=False,
                result=json.dumps(dict(audit_id='synthetic-skill-load'))))
            yield SimpleNamespace(event='ToolCallCompleted', run_id='offline', tool=SimpleNamespace(
                tool_name='search_market_evidence', tool_call_error=False,
                result=json.dumps(dict(facts=[], events=[], documents={}))))
            yield SimpleNamespace(event='RunContent', run_id='offline', content='Unsupported market outlook')
            yield SimpleNamespace(event='RunCompleted', run_id='offline')
    app.state.market.agent_factory = OfflineAgent
    with TestClient(app) as client:
        response = client.post('/api/market/ask', json={'message': 'Analyse City vacancy', 'mode': mode})
        events = [json.loads(s[6:]) for s in response.text.splitlines() if s.startswith('data: ')]
        assert events[-1]['type'] == 'done'
        assert events[-1]['metrics']['route']['mode'] == 'agent'
        assert events[-1]['publication_review']['semantic_approval'] is False
        assert events[-1]['publication_review']['status'] == 'withheld'
        assert 'Unsupported market outlook' not in ''.join(e['content'] for e in events if e['type'] == 'token')
    obs.close(wait=True)
    assert len(calls) == 1
    row, = receipts(tmp_path)
    assert row['actual_route']['mode'] == 'agent'
    assert row['status'] == ('ok' if provider_status == 200 else 'http_error')
