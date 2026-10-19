import time

from fastapi.testclient import TestClient

from london_product.runtime import create_app


def _wait(client, identity):
    for _ in range(100):
        row = client.get('/api/market/jobs/'+identity).json()
        if row['status'] not in ('queued', 'running'):
            return row
        time.sleep(.05)
    raise AssertionError('Research job did not settle')


def test_bounded_saved_research_uses_native_workflow_and_existing_report(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: (_ for _ in ()).throw(AssertionError('model invoked'))
    with TestClient(app) as client:
        response = client.post('/api/market/research/jobs',
                               json={'question': 'Research City vacancy in 2026 Q2'},
                               headers={'Idempotency-Key': 'research-one'})
        assert response.status_code == 202
        identity = response.json()['id']
        assert client.post('/api/market/research/jobs',
                           json={'question': 'Research City vacancy in 2026 Q2'},
                           headers={'Idempotency-Key': 'research-one'}).json()['id'] == identity
        result = _wait(client, identity)
        assert result['status'] == 'partial'
        assert result['run_id']
        assert result['result']['model_requests'] == 0
        report = client.get('/api/market/reports/'+result['result']['report_id']+'?format=json')
        assert report.status_code == 200
        assert report.json()['generation_status'] == 'insufficient_evidence'
        assert client.post('/api/market/research/jobs',
                           json={'question': 'Different question'},
                           headers={'Idempotency-Key': 'research-one'}).status_code == 422


def test_research_refresh_requires_one_registered_source(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False)
    with TestClient(app) as client:
        response = client.post('/api/market/research/jobs',
                               json={'question': 'Investigate City rents', 'refresh_sources': True})
    assert response.status_code == 422


def test_research_candidates_obey_metric_area_and_period(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False)
    store = app.state.market.store
    for identity, geo, period, metric in [('match','City','2026Q2','vacancy'),
                                          ('other-area','West End','2026Q2','vacancy'),
                                          ('other-period','City','2026Q1','vacancy'),
                                          ('other-metric','City','2026Q2','rent')]:
        store.put('facts',identity,{'id':identity,'metric':metric,'geography':geo,
            'period':period,'human_review_status':'pending_review',
            'evidence':{'quote':f'{geo} {metric} {period}'}})
    with TestClient(app) as client:
        response = client.post('/api/market/research/jobs',json={
            'question':'Research City vacancy in 2026 Q2'})
        result = _wait(client,response.json()['id'])
    assert result['status'] == 'partial'
    assert [row['record_id'] for row in result['result']['candidate_hits']] == ['match']
    assert result['result']['candidate_hits'][0]['scope_status'] == 'structured_match'


def test_deep_research_auto_route_returns_job_without_model(tmp_path):
    import json

    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: (_ for _ in ()).throw(AssertionError('model invoked'))
    with TestClient(app) as client:
        response = client.post('/api/market/ask',json={
            'message':'Deep research into City office vacancy in 2026 Q2', 'mode':'auto'},
            headers={'Idempotency-Key':'deep-one'})
        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        done = next(event for event in events if event['type']=='done')
        assert done['metrics']['route']['mode'] == 'research'
        assert done['metrics']['model_requests'] == 0
        job = _wait(client,done['research_job_id'])
        assert job['kind'] == 'research' and job['status'] == 'partial'
        assert job['result']['report_id']


def test_native_projection_without_report_remains_text(tmp_path):
    from london_product.safe_answer import project_run

    app = create_app(tmp_path, seed=False, scheduler=False)
    answer = project_run({'run_id': 'synthetic', 'agent_id': 'london-market-agent',
                          'status': 'COMPLETED', 'content': 'Unsupported draft',
                          'tools': []}, app.state.market.store)
    assert isinstance(answer['answer'], str)
    assert 'Unsupported draft' not in answer['answer']
    assert answer['publication_review']['status'] == 'withheld'
