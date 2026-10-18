import importlib.util
import pytest


def product():
    assert importlib.util.find_spec('london_product'), 'Product module missing'
    from london_product.store import Store
    from london_product.service import MarketService
    return Store, MarketService


def test_document_idempotence_and_restart(tmp_path):
    Store, _ = product()
    s = Store(tmp_path)
    a = s.snapshot({'id': 'official'}, 'https://example.org/report', b'original', 'text/html', [])
    b = s.snapshot({'id': 'official'}, 'https://example.org/alias', b'original', 'text/html', [])
    assert a['id'] == b['id']
    assert len(Store(tmp_path).all('documents')) == 1


def test_pending_fact_cannot_compare(tmp_path):
    Store, Service = product()
    s = Store(tmp_path)
    for i, period in enumerate(['2026Q1', '2026Q2']):
        s.put('facts', str(i), dict(id=str(i), metric='rent', value='95', unit='GBP/sqft/unknown',
            period=period, geography='City', status='needs_review', source_id='bnp'))
    result = Service(s).compare('0', '1')
    assert result['status'] == 'not_comparable'
    assert result['absolute_change'] is None


def test_event_dedup_and_report_escaping(tmp_path):
    Store, Service = product()
    s = Store(tmp_path)
    s.put('events', 'event', dict(title='<script>attack</script>', summary='Real excerpt', importance='high'))
    s.put('events', 'event', dict(title='duplicate'))
    svc = Service(s)
    assert len(s.all('events')) == 1
    report = svc.report('weekly')
    assert '<script>attack</script>' not in report['html']
    assert '&lt;script&gt;' in report['html']
    assert 'needs_review' in report['markdown']


def test_missing_notification_never_sent(tmp_path, monkeypatch):
    Store, Service = product()
    monkeypatch.delenv('LONDON_NOTIFICATION_URL', raising=False)
    s = Store(tmp_path); svc = Service(s)
    report = svc.report('daily')
    result = svc.notify(report['id'])
    assert result['status'] == 'configuration_missing'
    assert len(s.all('notifications')) == 1


def test_settings_validation_and_job_recovery(tmp_path):
    Store, Service = product()
    s = Store(tmp_path); svc = Service(s)
    with pytest.raises(ValueError): svc.save_settings({'news_interval_hours': 0})
    s.put('jobs', 'running', dict(status='running', kind='refresh', stage='fetch'))
    svc.recover_jobs()
    assert s.all('jobs')[0]['status'] == 'interrupted'


def test_exact_cadence_and_report_idempotence(tmp_path):
    Store, Service = product(); svc = Service(Store(tmp_path))
    with pytest.raises(ValueError): svc.save_settings({'news_interval_hours': 25})
    assert svc.save_settings({'news_interval_hours': 12})['news_interval_hours'] == 12
    first=svc.report('weekly', key='browser-click')
    assert svc.report('weekly', key='browser-click')['id']==first['id']


def test_threshold_events_require_review_and_deduplicate(tmp_path):
    Store, Service = product(); s=Store(tmp_path); svc=Service(s)
    base=dict(source_id='test',series='series',metric='vacancy',geography='City',
        definition='all physically vacant stock / stock',basis='quarter_end',grade='all',method='test-v1',currency=None,
        unit='percent',status='validated',human_review_status='approved')
    s.put('facts','old',dict(base,id='old',value='8.0',period='2026Q1'))
    s.put('facts','new',dict(base,id='new',value='8.6',period='2026Q2'))
    result=svc.monitor_changes()
    assert result['alerts']==1
    assert svc.monitor_changes()['alerts']==1
    assert len(s.all('events'))==1
    assert s.all('events')[0]['change_unit']=='pp'
    s.update('facts','new',{'human_review_status':'pending_review'})
    assert svc.monitor_changes()['alerts']==0


def test_per_run_model_budget_isolation_without_provider_calls():
    import asyncio
    from types import SimpleNamespace
    from london_product.intelligence import query_model
    model=query_model(); model._initial_budget.started-=500
    async def reserve_and_finish(identity):
        model._reserve((),dict(messages=[],run_response=SimpleNamespace(run_id=identity)))
        own=model.budget
        await asyncio.sleep(0)
        model.budget.after(10,2)
        assert model.budget is own
    asyncio.run(_parallel(reserve_and_finish('a'),reserve_and_finish('b')))
    assert model.budget_for('a').requests==1
    assert model.budget_for('a').input_tokens==10
    assert model.budget_for('b').input_tokens==10


async def _parallel(*calls):
    import asyncio
    await asyncio.gather(*calls)


def test_explicit_scale_normalization_records_rent_annual_basis():
    from london_product.normalization import derive
    takeup=derive(dict(metric='takeup',value='2.5',unit='m sq ft',period='Q1 2026',evidence={'quote':'take-up reached 2.5m sq ft in Q1 2026'}))
    assert takeup['raw_value']=='2.5' and takeup['normalized_value']=='2500000.0'
    assert takeup['normalized_unit']=='sqft' and takeup['normalized_period']=='2026Q1'
    assert takeup['normalized_precision']=='100000'
    # An area denominator alone does not prove an annual rent, but London office
    # headline rents are quoted per sq ft per annum by convention. The value is
    # used and the assumption is recorded, never silently applied.
    rent=derive(dict(metric='rent',value='95',unit='GBP/sqft',period='2026Q2',evidence={'quote':'Prime rents £95 per sq ft.'}))
    assert rent['annualization']=='industry_convention'
    assert rent['normalized_value']=='95' and rent['normalized_unit']=='GBP/sqft/year'
    assert 'ANNUAL_BASIS_ASSUMED_BY_CONVENTION' in rent['normalization_notes']
    assert 'ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED' not in rent['normalization_notes']
    # An explicit annual basis is recorded differently and needs no assumption.
    annual=derive(dict(metric='rent',value='95',unit='GBP/sqft',period='2026Q2',evidence={'quote':'Prime rents £95 per sq ft per annum.'}))
    assert annual['annualization']=='explicit'
    assert annual['normalized_value']=='95' and annual['normalized_unit']=='GBP/sqft/year'
    assert 'ANNUAL_BASIS_ASSUMED_BY_CONVENTION' not in annual['normalization_notes']
    # A rent with no area unit and no annual wording stays unresolved.
    unknown=derive(dict(metric='rent',value='95',unit='GBP',period='2026Q2',evidence={'quote':'Headline rent 95.'}))
    assert unknown['annualization']=='unknown' and unknown['normalized_value'] is None
    assert 'ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED' in unknown['normalization_notes']


def test_provider_usage_excess_rejected_after_response():
    from london_product.intelligence import Budget
    budget=Budget();budget.before(100,1800)
    with pytest.raises(ValueError,match='TOKEN_LIMIT_EXCEEDED'):budget.after(100,8001)
    assert budget.record()['output_tokens']==8001
    assert 'Provider reports' in budget.calls[-1]['usage_warning']


def test_successful_analysis_retry_is_cached(tmp_path):
    import hashlib,json
    Store,Service=product();svc=Service(Store(tmp_path))
    svc.store.put('facts','constructed-evidence-fixture',dict(value='8.4',metric='vacancy',status='pending_review'))
    fingerprint=hashlib.sha256(json.dumps(dict(facts=svc.facts(limit=500)['items'],events=[],prompt_version='report-analysis-v2'),sort_keys=True,default=str).encode()).hexdigest()
    svc.store.put('jobs','analysis:'+fingerprint,dict(kind='analysis',fingerprint=fingerprint,status='failed'))
    svc.store.put('jobs','retry-success',dict(kind='analysis',fingerprint=fingerprint,status='succeeded',result={'answer':'constructed cache fixture','run_id':'fixture','quality_status':'REVIEW_REQUIRED'}))
    assert svc.report_analysis()['cached'] is True  # No model factory is configured.


def test_concurrent_original_and_resource_key(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    Store, Service=product(); store=Store(tmp_path); svc=Service(store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        values=list(pool.map(lambda _:store.snapshot({'id':'test'},'https://example.org',b'same','text/html',[]),range(8)))
    assert len({v['id'] for v in values})==1
    monkeypatch.setattr(svc.pool,'submit',lambda *a:None)
    first=svc.submit('refresh',source_id='bnp',key='same')
    assert svc.submit('refresh',source_id='bnp',key='same')['id']==first['id']
    with pytest.raises(ValueError):svc.submit('refresh',source_id='jll',key='same')
    extract=svc.submit('extract',document_id='doc',key='one')
    assert svc.submit('extract',document_id='doc',key='two')['id']==extract['id']


# =============================================================================
# Regression tests for identified AI analysis fact errors
# =============================================================================

def test_prelet_share_cannot_be_mixed_with_supply_area(tmp_path):
    """prelet_share is a percentage, not sqft area. Mixing units is a fact error."""
    Store, Service = product()
    s = Store(tmp_path)
    # prelet_share: 80% - a ratio, not an area
    s.put('facts', 'prelet-q2', dict(
        metric='prelet_share', value='80', unit='percent', period='2026Q2',
        geography='Central London', status='pending_review', source_id='jll',
        definition='Share of delivered space pre-let or under offer; not solely pre-let'
    ))
    # supply: 21.6m sqft - an area
    s.put('facts', 'supply-q2', dict(
        metric='supply', value='21600000', unit='sqft', period='2026Q2',
        geography='Central London', status='pending_review', source_id='jll',
        definition='Available supply at quarter end'
    ))
    # These two metrics must NOT be compared - they are incompatible
    result = Service(s).compare('prelet-q2', 'supply-q2')
    assert result['status'] == 'not_comparable'
    assert 'MISMATCH_METRIC' in result['reasons'] or 'UNKNOWN_METRIC' in result['reasons']


def test_cross_publisher_supply_comparison_requires_same_source(tmp_path):
    """BNP Q1 supply and JLL Q2 supply are from different sources - no trend can be inferred."""
    Store, Service = product()
    s = Store(tmp_path)
    # BNP Q1: 22.8m sqft
    s.put('facts', 'bnp-q1', dict(
        metric='supply', value='22.8', unit='m sq ft', period='Q1 2026',
        geography='Central London', status='needs_review', source_id='bnp',
        definition='Available supply at quarter end', series='bnp', basis='quarter_end',
        grade=None, method='bnp-v1', currency=None
    ))
    # JLL Q2: 21.6m sqft (different source)
    s.put('facts', 'jll-q2', dict(
        metric='supply', value='21.6', unit='m sq ft', period='2026Q2',
        geography='Central London', status='pending_review', source_id='jll',
        definition='Available supply at quarter end', series='jll', basis='quarter_end',
        grade=None, method='jll-v1', currency=None
    ))
    result = Service(s).compare('bnp-q1', 'jll-q2')
    # Must be not_comparable because source_id differs (different publishers)
    assert result['status'] == 'not_comparable'
    assert 'MISMATCH_SERIES' in result['reasons'] or 'MISMATCH_SOURCE' in result['reasons'] or 'MISMATCH_METHOD' in result['reasons']


def test_agent_must_not_claim_all_vacancy_is_grade_a(tmp_path, monkeypatch):
    """Vacancy overall is not the same as Grade A vacancy - agent must not conflate them."""
    Store, Service = product()
    s = Store(tmp_path)
    # Overall vacancy: 8.4%
    s.put('facts', 'overall-vacancy', dict(
        metric='vacancy', value='8.4', unit='percent', period='2026Q1',
        geography='Central London', status='pending_review', source_id='bnp',
        definition='Overall office vacancy', grade='all'
    ))
    # Grade A share: 78%
    s.put('facts', 'grade-a-share', dict(
        metric='grade_a_share', value='78', unit='percent', period='Q1 2026',
        geography='Central London', status='needs_review', source_id='bnp',
        definition='of all take-up', grade='Grade A'
    ))
    # These are different metrics - cannot be compared
    result = Service(s).compare('overall-vacancy', 'grade-a-share')
    assert result['status'] == 'not_comparable'
    assert 'MISMATCH_METRIC' in result['reasons']


def test_agent_instructions_prohibit_source_count_claims(tmp_path):
    """Agent instructions explicitly prohibit claiming source counts or absent data."""
    from london_product.intelligence import query_agent
    Store, Service = product()
    s = Store(tmp_path)
    svc = Service(s)
    # Agent factory must use instructions that prohibit these errors
    agent = query_agent(svc, ':memory:')
    instructions = agent.instructions
    # Instructions must contain the anti-conflation guardrails
    combined = ' '.join(instructions) if isinstance(instructions, list) else instructions
    assert 'database-wide missing-data claim' in combined  # Do not claim absent data
    assert 'Do not invent source counts' in combined
    assert 'claim all vacancy is Grade A' in combined  # Anti-conflation guardrail


def test_same_publisher_consecutive_quarter_vacancy_is_comparable(tmp_path):
    """Same publisher, consecutive quarters, same metric = can be compared (pending_review blocks)."""
    Store, Service = product()
    s = Store(tmp_path)
    base = dict(
        metric='vacancy', unit='percent', geography='Central London (BNP source-defined office market)',
        status='pending_review', source_id='bnp', series='bnp', definition='Overall Central London office vacancy',
        basis='quarter_end', grade='overall; not restricted to Grade A', method='bnp-research-v1', currency=None
    )
    s.put('facts', 'q1', dict(base, id='q1', value='8.4', period='2026Q1'))
    s.put('facts', 'q2', dict(base, id='q2', value='8.4', period='2026Q2'))
    result = Service(s).compare('q1', 'q2')
    # Status should be not_comparable only because pending_review (not dimension mismatch)
    assert result['status'] == 'not_comparable'
    assert 'HUMAN_REVIEW_PENDING' in result['reasons']
    # NOT because of MISMATCH_SERIES, MISMATCH_GEOGRAPHY, etc.
    assert not any('MISMATCH' in r for r in result['reasons'] if r != 'HUMAN_REVIEW_PENDING')


def test_different_definitions_block_comparison_even_same_source(tmp_path):
    """Same source but different definitions (prime vs premium vs overall) block comparison."""
    Store, Service = product()
    s = Store(tmp_path)
    base = dict(
        metric='rent', unit='GBP/sqft/year', geography='City', period='2026Q2',
        status='pending_review', source_id='bnp', series='bnp', basis='quarter_end',
        method='bnp-research-v1', currency='GBP'
    )
    # Prime rent
    s.put('facts', 'prime', dict(base, id='prime', value='95', definition='prime', grade='prime'))
    # Premium rent
    s.put('facts', 'premium', dict(base, id='premium', value='110', definition='premium', grade='premium'))
    result = Service(s).compare('prime', 'premium')
    assert result['status'] == 'not_comparable'
    assert 'MISMATCH_DEFINITION' in result['reasons'] or 'MISMATCH_GRADE' in result['reasons']
