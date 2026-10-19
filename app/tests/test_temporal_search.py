"""The search projection must stay behind the existing evidence and review gates."""

from london_product.store import Store


def test_temporal_search_tracks_documents_facts_and_review_updates(tmp_path):
    store = Store(tmp_path)
    source = store.put('sources', 'publisher', {'name': 'Example Research'})
    document = store.put('documents', 'report', {
        'source_id': source['id'], 'title': 'London Q2 report',
        'url': 'https://example.org/q2', 'published_at': '2026-07-15',
        'geography': 'City', 'period': '2026Q2',
        'segments': [{'page': 4, 'text': 'City leasing take-up reached 2.1 million square feet.'}],
    })
    fact = store.put('facts', 'city-takeup', {
        'source_id': source['id'], 'document_id': document['id'],
        'metric': 'takeup', 'geography': 'City', 'period': '2026Q2',
        'value': '2.1', 'unit': 'million sqft', 'status': 'pending_review',
        'human_review_status': 'pending_review',
        'evidence': {'page': 4, 'quote': 'City leasing take-up reached 2.1 million square feet.'},
    })
    found = store.search_evidence('leasing take-up', geography='City', period='2026Q2')
    assert {row['record_id'] for row in found} == {document['id'], fact['id']}
    assert any(row['record_type'] == 'document' and row['locator'] == 'page:4' for row in found)
    assert any(row['record_type'] == 'fact' and row['review_status'] == 'pending_review' for row in found)
    assert store.search_evidence('leasing', review_status='approved') == []

    store.update('facts', fact['id'], {'human_review_status': 'approved', 'status': 'validated'})
    approved = store.search_evidence('leasing', record_type='fact', review_status='approved')
    assert len(approved) == 1 and approved[0]['record_id'] == fact['id']
    assert store.search_evidence('leasing', record_type='fact', review_status='pending_review') == []
    assert len(Store(tmp_path).search_evidence('leasing', record_type='fact')) == 1


def test_search_is_bounded_idempotent_and_treats_input_as_text(tmp_path):
    store = Store(tmp_path)
    payload = {'metric': 'vacancy', 'geography': 'West End', 'period': '2026Q1',
               'status': 'needs_review', 'evidence': {'quote': 'West End vacancy rate was 6.1%.'}}
    fact = store.put('facts', 'one', payload)
    assert store.put('facts', 'one', {'evidence': {'quote': 'False revision'}})['id'] == fact['id']
    assert len(store.search_evidence('vacancy')) == 1
    assert store.search_evidence('vacancy', geography='City') == []
    assert store.search_evidence('vacancy', period='2026Q2') == []
    assert store.search_evidence('vacancy', metric='rent') == []
    assert store.search_evidence('vacancy" OR *') == store.search_evidence('vacancy')
    assert store.search_evidence('') == []
    assert len(store.search_evidence('vacancy', limit=10000)) == 1


def test_existing_records_are_backfilled_once(tmp_path):
    store = Store(tmp_path)
    fact = store.put('facts', 'old', {'metric': 'supply', 'geography': 'City',
                                    'period': '2026Q1', 'evidence': {'quote': 'Refurbishment pipeline.'}})
    with store.engine.begin() as connection:
        connection.exec_driver_sql('DELETE FROM market_search')
        connection.exec_driver_sql('DELETE FROM product_schema WHERE version=3')
    restarted = Store(tmp_path)
    assert restarted.search_evidence('refurbishment')[0]['record_id'] == fact['id']
    assert len(Store(tmp_path).search_evidence('refurbishment')) == 1


def test_search_api_returns_saved_evidence_without_model(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app

    app = create_app(tmp_path, seed=False, scheduler=False)
    app.state.market.agent_factory = lambda: (_ for _ in ()).throw(AssertionError('model invoked'))
    app.state.market.store.put('facts', 'saved', {
        'metric': 'employment', 'geography': 'London', 'period': '2026Q2',
        'human_review_status': 'pending_review',
        'evidence': {'quote': 'London employment observation.'},
    })
    with TestClient(app) as client:
        response = client.get('/api/market/search', params={'q': 'employment', 'metric': 'employment'})
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['review_status'] == 'pending_review'
    assert response.json()['model_requests'] == 0
