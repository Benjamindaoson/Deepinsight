"""Saved chat uses a native, model-free Agno Workflow rather than a fake run ID."""

import json
import pytest

from fastapi.testclient import TestClient

from london_product.runtime import create_app
from london_product.intelligence import run_saved_query_workflow
from test_foundation import fact


def _events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_focused_saved_answer_has_native_workflow_run(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)
    response = TestClient(app).post('/api/market/ask', json={
        'message': 'What is the latest City vacancy rate?', 'mode': 'saved',
    })
    assert response.status_code == 200
    events = _events(response)
    done = next(event for event in events if event.get('type') == 'done')
    assert done['run_id']
    assert done['execution_path'] == 'agno_workflow'
    assert done['metrics']['model_requests'] == 0
    assert any(event.get('type') == 'token' and event.get('content') for event in events)
    assert app.state.market.query_workflow.id == 'london-saved-query-workflow'


def test_saved_report_context_has_native_workflow_run(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)
    response = TestClient(app).post('/api/market/ask', json={
        'message': 'Explain the latest London office market changes and risks.',
        'mode': 'saved',
    })
    assert response.status_code == 200
    events = _events(response)
    done = next(event for event in events if event.get('type') == 'done')
    assert done['run_id']
    assert done['execution_path'] == 'agno_workflow'
    assert done['metrics']['model_requests'] == 0
    assert done['report_id']
    assert app.state.market.store.get('reports', done['report_id'])


def test_live_agentos_registers_saved_query_with_other_native_workflows(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False)
    workflow_ids = {workflow.id for workflow in app.state.agent_os.workflows}
    assert {'london-saved-query-workflow', 'london-monitor-workflow',
            'london-report-workflow'} <= workflow_ids


def test_saved_query_fails_closed_without_native_workflow(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)
    app.state.market.query_workflow = None
    with pytest.raises(RuntimeError, match='SAVED_QUERY_WORKFLOW_NOT_CONFIGURED'):
        run_saved_query_workflow(app.state.market, 'focused', question='City vacancy')


def test_manual_comparison_uses_native_workflow_without_approving_facts(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)
    store = app.state.market.store
    store.put('facts', 'old', fact(id='old', human_review_status='pending_review'))
    store.put('facts', 'new', fact(id='new', value='95', period='2026Q2',
                                   human_review_status='pending_review'))
    response = TestClient(app).post('/api/market/compare', json={
        'old_id': 'old', 'new_id': 'new',
    })
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'not_comparable'
    assert 'HUMAN_REVIEW_PENDING' in result['reasons']
    assert result['execution_path'] == 'agno_workflow'
    assert result['run_id']
    assert store.get('facts', 'old')['human_review_status'] == 'pending_review'
