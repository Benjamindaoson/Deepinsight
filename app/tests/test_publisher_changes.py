"""Real saved source replay and negative attribution checks; no provider calls."""
import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from london_product.store import Store
from london_product.service import MarketService

ROOT = Path(__file__).parents[2]
DOC_ID = 'doc-jll-e2eaadc6049e717d5ebc'


@pytest.fixture
def real_service(tmp_path):
    store = Store(tmp_path)
    # A regression fixture must not run live Store migrations or enable WAL.
    with sqlite3.connect((ROOT/'app/data/product/market.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        for table,identity in [('sources','jll'),('documents',DOC_ID)]:
            raw=db.execute(f'SELECT payload FROM {table} WHERE id=? OR identity=?',(identity,identity)).fetchone()[0]
            store.put(table,identity,json.loads(raw))
    service = MarketService(store)
    yield service
    service.pool.shutdown(wait=True)


def test_real_source_change_is_attributed_not_calculated_or_approved(real_service):
    service = real_service
    service.monitor_changes()
    changes = [e for e in service.store.all('events') if e.get('kind') == 'publisher_reported_change']
    assert len(changes) == 1
    item = changes[0]
    assert item['classification'] == 'publisher_reported_change'
    assert item['reported_change'] == '15' and item['change_unit'] == 'percent'
    assert item['period'] == '2026Q2' and item['comparison_period'] == '2026Q1'
    assert item['human_review_status'] == 'pending_review'
    assert item['calculation_performed'] is False and item['system_change_value'] is None
    doc = service.store.get('documents', item['document_id'])
    assert hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest() == item['document_sha256']
    assert item['evidence']['quote'] in next(s['text'] for s in doc['segments'] if s['page'] == 1)
    before = json.dumps(item, sort_keys=True)
    service.monitor_changes()
    assert len(service.store.all('events')) == 1
    assert json.dumps(service.store.get('events', item['id']), sort_keys=True) == before
    assert service.store.all('facts') == []


def test_change_reaches_report_and_compact_evidence_without_approval(real_service):
    from london_product.qa_context import evidence_pack
    real_service.monitor_changes()
    report = real_service.report('weekly', key='test')
    assert 'publisher_reported_change' in report['markdown']
    assert '15%' in report['markdown'] and 'not a system-calculated change' in report['markdown']
    pack = evidence_pack(real_service, '最近一个季度有哪些变化风险和机会', {'facts': [], 'events': []})
    assert len(pack['publisher_reported_changes']) == 1
    assert pack['coverage']['approved_fact_records'] == 0
    assert 'publisher_reported_change' in pack['answer_constraint']
    assert len(json.dumps(pack, ensure_ascii=False).encode()) <= 12000


def test_legacy_identity_record_is_not_duplicated(real_service):
    """A change already saved under an older identity scheme must not re-duplicate."""
    service = real_service
    doc = service.store.get('documents', DOC_ID)
    quote = next(s['text'] for s in doc['segments'] if s['page'] == 1)
    from london_product.publisher_changes import TAKEUP
    match = TAKEUP.search(quote)
    legacy = service.store.put('events', 'legacy-random-id', dict(
        kind='publisher_reported_change', classification='publisher_reported_change',
        title='JLL reported Central London take-up up 15% quarter-on-quarter · 2026Q2',
        status='pending_review', human_review_status='pending_review',
        document_sha256=doc['sha256'], evidence=dict(quote=match.group())))
    service.monitor_changes()
    changes = [e for e in service.store.all('events') if e.get('kind') == 'publisher_reported_change']
    assert len(changes) == 1
    assert changes[0]['id'] == legacy['id']
    service.monitor_changes()
    assert len([e for e in service.store.all('events') if e.get('kind') == 'publisher_reported_change']) == 1


def test_hash_mismatch_never_creates_market_change(real_service, tmp_path):
    doc = real_service.store.get('documents', DOC_ID)
    broken = tmp_path / 'modified.pdf'; broken.write_bytes(b'altered')
    real_service.store.update('documents', doc['id'], {'path': str(broken)})
    real_service.monitor_changes()
    assert real_service.store.all('events') == []


def test_incomplete_or_forecast_text_is_not_a_reported_change(real_service):
    doc = real_service.store.get('documents', DOC_ID)
    # A page without the exact reported observation cannot become a change.
    real_service.store.update('documents', doc['id'], {'segments': [dict(page=1, locator='pdf:page:1', text='Outlook: take-up may rise 15% next quarter.')]})
    real_service.monitor_changes()
    assert real_service.store.all('events') == []


def test_report_keeps_combined_transaction_definition(real_service):
    original = real_service.store.put('facts', 'combined', dict(metric='prelet_share', geography='Central London',
        period='2026Q2', value='80', unit='percent', status='pending_review', document_id=DOC_ID,
        definition='Share of delivered space pre-let or under offer',
        evidence={'quote': '80% of delivered space pre-let or under offer', 'page': 1, 'locator': 'pdf:page:1'}))
    report = real_service.report('weekly')
    assert 'Share of delivered space pre-let or under offer' in report['markdown']
    assert 'pdf:page:1' in report['markdown']
    assert real_service.store.get('facts', original['id']) == original


def test_rejected_events_cannot_reappear_in_report(real_service):
    real_service.monitor_changes()
    change = real_service.store.all('events')[0]
    real_service.store.update('events', change['id'], {'human_review_status': 'rejected'})
    real_service.store.put('events', 'rejected-news', dict(title='Rejected leasing headline', kind='lease',
        status='rejected', document_id=DOC_ID, evidence={'quote': 'Rejected event'}))
    report = real_service.report('weekly')
    assert change['title'] not in report['markdown']
    assert 'Rejected leasing headline' not in report['markdown']


@pytest.mark.parametrize('metric,query', [('availability','City availability'), ('inflation_rate','inflation'), ('prelet','supply')])
def test_contract_metrics_are_retrievable(real_service, metric, query):
    from london_product.qa_context import evidence_pack
    fact = real_service.store.put('facts', metric, dict(metric=metric, geography='City', period='2026Q2',
        value='1', unit='unknown', status='needs_review', document_id=DOC_ID, source_id='jll',
        evidence={'quote':'Fixture for routing only', 'locator':'fixture'}))
    pack=evidence_pack(real_service, query, dict(facts=[],events=[]))
    assert [f['id'] for f in pack['facts']] == [fact['id']]


def test_human_rejected_event_never_enters_model_evidence(real_service):
    from london_product.qa_context import evidence_pack
    doc=real_service.store.get('documents',DOC_ID)
    quote=doc['segments'][0]['text'][:100]
    real_service.store.put('events','rejected-event',dict(source_id='jll',document_id=DOC_ID,
        kind='lease',status='pending_review',human_review_status='rejected',title='Rejected',evidence={'quote':quote}))
    pack=evidence_pack(real_service,'news events',dict(facts=[],events=[]))
    assert pack['events']==[]
