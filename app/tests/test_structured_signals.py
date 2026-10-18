"""Contract checks for new public structured feeds and foreground routing.

The HTTP fixtures are offline. Live acquisition is recorded separately in the
product evidence directory; these tests do not claim API availability.
"""
import asyncio
import json

import httpx
import pytest

from london_product.routing import route_question
from london_product.sources import catalog, fetch_source, parse_content
from london_product.store import Store
from london_product.service import MarketService
from london_product.structured_sources import nomis_employment, planning_events, segments


def test_planning_api_requires_office_evidence_and_preserves_status(tmp_path):
    source = next(row for row in catalog() if row['id'] == 'planning-api-city')
    body = json.dumps({'hits': {'hits': [
        {'_id': 'CITY-1', '_source': {'lpa_name': 'City of London',
         'description': 'Additional office floorspace (Use Class E) at 1 Example Street.',
         'status': 'Pending decision', 'lpa_app_no': '26/0001'}},
        {'_id': 'CITY-2', '_source': {'lpa_name': 'City of London',
         'description': 'Home office extension on Example Road.', 'status': 'Approved'}},
        {'_id': 'CITY-3', '_source': {'lpa_name': 'Westminster',
         'description': 'Commercial office building.', 'status': 'Approved'}},
    ]}}).encode()
    store = Store(tmp_path)
    doc = store.snapshot(source, source['url'], body, 'application/json', segments(source, body))
    assert planning_events(store, doc, source, body) == 1
    assert planning_events(store, doc, source, body) == 0
    events = store.all('events')
    assert len(events) == 1
    event = events[0]
    assert event['status'] == event['human_review_status'] == 'pending_review'
    assert event['application_status'] == 'Pending decision'
    assert event['evidence']['locator'] == 'json:/hits/hits/0/_source/description'
    assert event['document_id'] == doc['id']
    assert event['interpretation_limit'].startswith('Planning status is not')


def test_nomis_annual_jobs_not_office_demand_and_idempotent(tmp_path):
    source = next(row for row in catalog() if row['id'] == 'nomis-london')
    body = (b'DATE,GEOGRAPHY_NAME,INDUSTRY_NAME,EMPLOYMENT_STATUS_NAME,OBS_VALUE\n'
            b'2023,London,Total,Employment,5778000\n'
            b'2024,London,Total,Employment,5887000\n')
    store = Store(tmp_path)
    doc = store.snapshot(source, source['url'], body, 'text/csv', parse_content(body, 'text/csv'))
    assert nomis_employment(store, doc, source, body) == 2
    assert nomis_employment(store, doc, source, body) == 2
    facts = store.all('facts')
    assert len(facts) == 2
    assert {f['period'] for f in facts} == {'2023', '2024'}
    assert all(f['unit'] == 'jobs' and f['status'] == 'pending_review' for f in facts)
    assert all(f['eligible_for_comparison'] is False for f in facts)
    assert all('all industries' in f['definition'] for f in facts)
    assert all(f['evidence']['quote'] in [s['text'] for s in doc['segments']] for f in facts)
    answer, citations = MarketService(store).saved_answer('查看伦敦就业数据')
    assert '5887000 jobs [pending_review]' in answer
    assert 'United Kingdom' not in answer
    assert 'csv:row:3' in answer
    assert citations and all(c['document_id'] == doc['id'] for c in citations)


def test_structured_feed_fails_closed_on_changed_schema(tmp_path):
    source = next(row for row in catalog() if row['id'] == 'planning-api-city')
    with pytest.raises(ValueError, match='PLANNING_SCHEMA_INVALID'):
        segments(source, b'{"hits":{"hits":[null]}}')
    source = next(row for row in catalog() if row['id'] == 'nomis-london')
    body = b'DATE,GEOGRAPHY_NAME,INDUSTRY_NAME,EMPLOYMENT_STATUS_NAME,OBS_VALUE\n2024,Manchester,Total,Employment,5\n'
    store = Store(tmp_path)
    doc = store.snapshot(source, source['url'], body, 'text/csv', parse_content(body, 'text/csv'))
    with pytest.raises(ValueError, match='NOMIS_SERIES_MISMATCH'):
        nomis_employment(store, doc, source, body)
    assert store.all('facts') == []


def test_nomis_revision_preserves_old_original_and_review_gate(tmp_path):
    source = next(row for row in catalog() if row['id'] == 'nomis-london')
    store = Store(tmp_path)
    for value in (5887000, 5888000):
        body = (b'DATE,GEOGRAPHY_NAME,INDUSTRY_NAME,EMPLOYMENT_STATUS_NAME,OBS_VALUE\n'
                + f'2024,London,Total,Employment,{value}\n'.encode())
        doc = store.snapshot(source, source['url'], body, 'text/csv', parse_content(body, 'text/csv'))
        nomis_employment(store, doc, source, body)
    rows = store.all('facts')
    assert len(rows) == 2
    active = next(row for row in rows if row['status'] != 'superseded')
    old = next(row for row in rows if row['status'] == 'superseded')
    assert old['superseded_by'] == active['id']
    assert active['status'] == 'pending_review'
    assert old['human_review_status'] == 'pending_review'
    assert store.get('documents', old['document_id'])['sha256'] != store.get('documents', active['document_id'])['sha256']


def test_epc_missing_token_never_attempts_network(monkeypatch):
    from london_product import sources
    monkeypatch.delenv('LONDON_EPC_TOKEN', raising=False)
    monkeypatch.setattr(sources, '_make_transport', lambda: pytest.fail('network attempted'))
    source = next(row for row in catalog() if row['id'] == 'epc-nondomestic')
    assert source['health'] == 'configuration_missing'
    with pytest.raises(ValueError, match='CONFIGURATION_MISSING'):
        asyncio.run(fetch_source(dict(source, enabled=True)))


def test_planning_header_is_only_sent_to_fixed_official_endpoint(monkeypatch):
    from london_product import sources
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={'hits': {'hits': []}})
    monkeypatch.setattr(sources, '_make_transport', lambda: httpx.MockTransport(respond))
    source = next(row for row in catalog() if row['id'] == 'planning-api-city')
    asyncio.run(fetch_source(source))
    assert seen[0].headers['x-api-allowrequest'] == 'be2rmRnt&'
    with pytest.raises(ValueError, match='SOURCE_POLICY'):
        asyncio.run(fetch_source(dict(source, url='https://www.jll.com/report')))


@pytest.mark.parametrize(('question', 'mode'), [
    ('查看伦敦就业数据', 'saved'),
    ('最新规划项目有哪些？', 'saved'),
    ('Compare City prime rents', 'saved'),
    ('最近一个季度有哪些变化、风险和机会？', 'agent'),
    ('Why is office demand shifting?', 'agent'),
])
def test_intent_route_avoids_model_for_simple_lookup(question, mode):
    assert route_question(question)['mode'] == mode
