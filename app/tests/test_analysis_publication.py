"""Publication safety regressions, including replay of real saved provider failures."""
import hashlib
import json
from pathlib import Path
import pytest
from london_product.store import Store
from london_product.service import MarketService

EVIDENCE = Path(__file__).parents[1] / 'data/product/evidence'


@pytest.mark.parametrize('version,codes', [
    ('v1', {'MODEL_SOURCE_COUNT', 'UNVERIFIED_MARKET_TREND'}),
    ('v2', {'LEASE_STATUS_QUANTITY', 'UNVERIFIED_MARKET_TREND'}),
])
def test_real_failed_outputs_are_not_republished(tmp_path, version, codes):
    from london_product.analysis_guard import review_analysis
    original = json.loads((EVIDENCE / f'ai-report-analysis-{version}.json').read_text(encoding='utf-8'))['result']['answer']
    result = review_analysis(original, Store(tmp_path))
    assert result['raw_answer'] == original
    assert result['raw_sha256'] == hashlib.sha256(original.encode()).hexdigest()
    assert codes <= set(result['publication_review']['codes'])
    assert result['publication_review']['status'] == 'withheld'
    assert 'pre-let over 4,300' not in result['answer']
    assert 'contracted to 21.6' not in result['answer']
    assert '5 unique URLs' not in result['answer']
    assert result['quality_status'] == 'REVIEW_REQUIRED'


@pytest.mark.parametrize('text,code', [
    ('GPE pre-let 4,300 sq ft, with another floor under offer.', 'LEASE_STATUS_QUANTITY'),
    ('已预租面积为 4300 平方英尺，另有一层洽谈中。', 'LEASE_STATUS_QUANTITY'),
    ('BNP Q1 supply 22.8m; JLL Q2 supply 21.6m. Supply declined.', 'UNVERIFIED_MARKET_TREND'),
    ('伦敦供应由 22.8 降至 21.6 百万平方英尺。', 'UNVERIFIED_MARKET_TREND'),
    ('Source count: five unique URLs.', 'MODEL_SOURCE_COUNT'),
    ('本次共引用 5 个来源。', 'MODEL_SOURCE_COUNT'),
])
def test_untrusted_claim_variants(tmp_path, text, code):
    from london_product.analysis_guard import review_analysis
    result = review_analysis(text, Store(tmp_path))
    assert code in result['publication_review']['codes']
    assert text not in result['answer']


def test_candidate_series_cannot_release_unverified_model_trend(tmp_path):
    from london_product.analysis_guard import review_analysis
    store = Store(tmp_path)
    for year, value in [('2023', '5778000'), ('2024', '5887000')]:
        store.put('facts', year, dict(id=year, metric='employment', geography='London (workplace)',
            definition='All-industry workplace employment', unit='jobs', period=year,
            source_id='synthetic',series='synthetic-jobs',method='synthetic-method',basis='annual',grade='all',currency=None,
            value=value, status='pending_review', human_review_status='pending_review'))
    raw = 'London office supply declined and prime rent increased this quarter.'
    result = review_analysis(raw, store)
    assert result['directional']['status'] == 'available'
    assert result['publication_review']['status'] == 'withheld'
    assert raw not in result['answer']
    assert result['quality_status'] == 'REVIEW_REQUIRED'


def test_inventory_distinguishes_entries_documents_urls_and_contributors(tmp_path):
    from london_product.analysis_guard import source_inventory, review_analysis
    store = Store(tmp_path)
    for sid in ['bnp', 'gpe', 'unavailable']:
        store.put('sources', sid, {'id': sid})
    for did, sid, url in [('d1','bnp','https://example.org/q1'), ('d2','bnp','https://example.org/q2'), ('d3','bnp','https://example.org/q2'), ('d4','gpe','https://example.org/event')]:
        store.put('documents', did, {'id': did, 'source_id': sid, 'url': url})
    store.put('facts', 'f', {'source_id': 'bnp', 'status': 'pending_review'})
    store.put('events', 'e', {'source_id': 'gpe', 'status': 'pending_review', 'kind': 'owner_leasing'})
    inventory = source_inventory(store)
    assert inventory == dict(registered_source_entries=3, entries_with_saved_documents=2,
        saved_document_snapshots=4, distinct_saved_urls=3, active_fact_event_source_entries=2)
    result = review_analysis('Further evidence would be needed to evaluate this hypothesis.', store)
    assert result['publication_review']['status'] == 'limited_checks_passed'
    assert result['quality_status'] == 'REVIEW_REQUIRED'
    assert 'Registered source entries: 3' in result['answer']


def test_event_context_preserves_under_offer_without_mutating_original(tmp_path):
    from london_product.analysis_guard import event_context
    store = Store(tmp_path)
    text = 'GPE has pre let the initial floor, with a further floor under offer. The transactions total more than 4,300 sq ft. Later commentary.'
    store.put('documents','d',dict(id='d',sha256='digest',url='https://example.org/gpe',segments=[dict(text=text,locator='html:main')]))
    event = dict(document_id='d', summary='The transactions total more than 4,300 sq ft.', evidence={'quote':'The transactions total more than 4,300 sq ft.'})
    original = json.dumps(event, sort_keys=True)
    context = event_context(event, store)
    assert 'a further floor under offer' in context['quote']
    assert context['quote'] in text
    assert context['document_sha256'] == 'digest'
    assert json.dumps(event, sort_keys=True) == original


def test_report_cannot_bypass_guard_with_supplied_analysis(tmp_path):
    service = MarketService(Store(tmp_path))
    analysis = dict(answer='GPE pre-let over 4,300 sq ft.', run_id='fixture-run')
    report = service.report('weekly', analysis=analysis)
    assert 'GPE pre-let over 4,300' not in report['markdown']
    assert 'withheld' in report['markdown']
    assert analysis['answer'] == 'GPE pre-let over 4,300 sq ft.'


def test_historical_report_read_is_guarded_and_does_not_rewrite_record(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app = create_app(tmp_path, seed=False, scheduler=False)
    store = app.state.market.store
    raw = 'Great Portland Estates pre-let over 4,300 sq ft.'
    markdown = '# Saved report\n\n## Optional AI interpretation — REVIEW_REQUIRED\n'+raw+'\nNative analysis Run: original-run'
    report = store.put('reports','old',dict(markdown=markdown,html='<html>'+markdown+'</html>',analysis_id='missing',period='weekly'))
    before = store.get('reports',report['id'])
    with TestClient(app) as client:
        for fmt in ['markdown','html']:
            response = client.get('/api/market/reports/'+report['id']+'?format='+fmt)
            assert response.status_code == 200
            assert raw not in response.text
            assert 'withheld' in response.text
    assert store.get('reports',report['id']) == before


def test_cached_bad_analysis_is_reviewed_without_model_or_record_change(tmp_path):
    store = Store(tmp_path)
    service = MarketService(store)
    store.put('facts','f',dict(metric='takeup',status='pending_review'))
    fingerprint = hashlib.sha256(json.dumps(dict(facts=service.facts(limit=500)['items'],events=[],prompt_version='report-analysis-v2'),sort_keys=True,default=str).encode()).hexdigest()
    original = store.put('jobs','analysis:'+fingerprint,dict(kind='analysis',status='succeeded',fingerprint=fingerprint,
        result=dict(answer='Source count: 5 unique URLs.',run_id='original')))
    result = service.report_analysis()  # No agent factory: any model call fails.
    assert result['cached'] is True
    assert result['publication_review']['status'] == 'withheld'
    assert store.get('jobs',original['id']) == original


@pytest.mark.parametrize('complete', [True, False])
def test_sse_does_not_leak_raw_claims_even_on_incomplete_run(tmp_path, complete):
    """Synthetic stream transport test; not a real model capability evaluation."""
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app = create_app(tmp_path,seed=False,scheduler=False)
    store = app.state.market.store
    store.put('documents','d',dict(url='https://example.org/gpe',source_id='gpe'))
    raw = 'GPE pre-let over 4,300 sq ft. https://example.org/gpe'
    class Budget:
        def record(self): return dict(requests=0,fixture=True)
    class Agent:
        model = SimpleNamespace(budget_for=lambda _: Budget())
        async def arun(self,*args,**kwargs):
            for content in [raw[:20],raw[20:]]:
                yield SimpleNamespace(event='RunContent',content=content,run_id='fixture-run')
            if complete:
                yield SimpleNamespace(event='RunCompleted',content=None,run_id='fixture-run')
    app.state.market.agent_factory = Agent
    with TestClient(app) as client:
        response = client.post('/api/market/ask',json=dict(message='Show leasing',mode='agent'))
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    published = ''.join(e.get('content','') for e in events if e['type']=='token')
    assert raw not in published
    assert 'pre-let over 4,300' not in published
    if complete:
        assert 'withheld' in published
        result = store.all('jobs')[0]
        assert result['result']['raw_answer'] == raw
        assert result['metrics']['provider_ttft_seconds'] <= result['metrics']['ttft_seconds']
    else:
        assert published == ''
        assert events[-1]['type'] == 'error'
