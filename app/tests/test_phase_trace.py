import json

from london_product.phase_trace import PhaseTrace, summarize


def test_trace_records_only_bounded_timing_and_no_question(tmp_path):
    trace = PhaseTrace(tmp_path, 'ask', 'What is the rent in City?', 'saved')
    trace.mark('routing')
    trace.mark('evidence')
    receipt = trace.finish('succeeded', model_requests=0)
    assert receipt['phases_ms']['routing'] >= 0
    assert receipt['total_ms'] >= receipt['phases_ms']['routing']
    raw = (tmp_path/'traces'/'phases.jsonl').read_text()
    assert 'What is the rent' not in raw
    assert json.loads(raw)['model_requests'] == 0
    summary = summarize(tmp_path)
    assert summary['count'] == 1 and summary['p95_ms'] == receipt['total_ms']


def test_trace_summary_reports_real_distribution(tmp_path):
    for value in range(20):
        trace = PhaseTrace(tmp_path, 'ask', str(value), 'saved')
        trace.finish('succeeded', model_requests=0)
    summary = summarize(tmp_path)
    assert summary['count'] == 20
    assert summary['p95_ms'] >= summary['p50_ms'] >= 0
    assert summary['basis'] == 'observed_local_runs'


def test_saved_ask_exposes_observed_latency_without_model(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app

    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: (_ for _ in ()).throw(AssertionError('model invoked'))
    with TestClient(app) as client:
        response = client.post('/api/market/ask', json={'message': 'Show City rent', 'mode': 'saved'})
        assert response.status_code == 200 and '"type": "done"' in response.text
        stats = client.get('/api/market/performance', params={'kind': 'ask', 'route': 'saved'})
    assert stats.status_code == 200
    assert stats.json()['count'] == 1
    assert stats.json()['p95_ms'] is not None


def test_telemetry_storage_failure_never_blocks_answer(tmp_path):
    (tmp_path/'traces').write_text('occupied')
    receipt = PhaseTrace(tmp_path, 'ask', 'safe', 'saved').finish('succeeded')
    assert receipt['status'] == 'succeeded' and receipt['persisted'] is False
