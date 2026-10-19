"""Per-finding verification, positive analysis path, consistency and monitoring loop."""
import pytest
from london_product.store import Store
from london_product.service import MarketService


@pytest.fixture
def svc(tmp_path):
    service = MarketService(Store(tmp_path))
    yield service
    service.pool.shutdown(wait=True)


def observation(svc, identity, *, geography='City', period='2026Q2', value='8', approved=True,
                definition='vacant stock share', metric='vacancy', unit='percent'):
    quote = f'{geography} {period}: {value} {unit}. Explicit source observation.'
    store = svc.store
    store.put('sources', 'official', dict(id='official', name='Official', allow_llm=True))
    doc = store.snapshot(dict(id='official', name='Official'), 'https://example.org/'+identity,
        quote.encode(), 'text/plain', [dict(segment_id='p1', text=quote, page=1, locator='page 1')], published_at='2026-07-01')
    return store.put('facts', identity, dict(id=identity, source_id='official', document_id=doc['id'],
        metric=metric, geography=geography, period=period, value=value, unit=unit, series='quarterly',
        definition=definition, basis='quarter_end', grade='all', method='survey', currency=None,
        status='validated' if approved else 'pending_review', human_review_status='approved' if approved else 'pending_review',
        evidence=dict(quote=quote, page=1, locator='page 1')))


def test_deterministic_findings_carry_verification(svc):
    from london_product.chat_report import build_report
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    assert report['key_findings']
    for f in report['key_findings']+report['executive_summary']+report['outlook']:
        assert f['origin']=='deterministic'
        assert f['verification']['status']=='verified', f['verification']
        assert f['verification']['verifier'].startswith('finding-verifier-')


def test_verifier_unit_rejections(svc):
    from london_product.chat_report import build_report
    from london_product.finding_verification import verify_finding
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    def verdict(text, ids=['v'], classification='inference'):
        return verify_finding(dict(text=text,classification=classification,evidence_ids=ids),report,svc.store)
    assert verdict('City vacancy is 8 percent in 2026Q2; monitor.')['status']=='verified'
    assert 'QUANTITATIVE_CLAIM_MISMATCH' in verdict('Vacancy reached 99 percent.')['reasons']
    assert 'AUTHORITY_STATUS_CLAIM' in verdict('This figure is approved and human-reviewed.')['reasons']
    assert 'AUTHORITY_STATUS_CLAIM' in verdict('该数据已人工审核通过。')['reasons']
    assert 'COVERAGE_CLAIM' in verdict('All metrics are fully covered with no gaps.')['reasons']
    assert 'SOURCE_COUNT_CLAIM' in verdict('Three sources confirm the market.')['reasons']
    assert 'UNVERIFIED_MULTIPLIER_CLAIM' in verdict('Rents will triple next year.')['reasons']
    assert 'CAUSAL_CLAIM_REQUIRES_REVIEW' in verdict('Demand caused vacancy to fall.')['reasons']
    assert 'GEOGRAPHY_MISMATCH' in verdict('West End vacancy is 8 percent in 2026Q2.')['reasons']
    assert 'PERIOD_MISMATCH' in verdict('City vacancy is 8 percent in 2025Q4.')['reasons']
    assert 'EVIDENCE_ID_UNKNOWN' in verdict('A cautious hypothesis.',ids=['invented'])['reasons']
    assert 'EVIDENCE_MISSING' in verdict('A cautious hypothesis.',ids=[])['reasons']
    assert 'DIRECTION_WITHOUT_COMPARISON' in verdict('City vacancy is rising; monitor.')['reasons']
    assert 'MODEL_FACT_PROMOTION_BLOCKED' in verdict('City vacancy is 8 percent.',classification='fact')['reasons']


def test_direction_must_agree_with_cited_calculation(svc):
    from london_product.chat_report import build_report
    from london_product.finding_verification import verify_finding
    observation(svc,'old',period='2026Q1',value='9')
    observation(svc,'new',period='2026Q2',value='8')
    report=build_report(svc,'Analyse City vacancy Q2 2026 historical trend')
    calc=report['calculations'][0]
    def verdict(text):
        return verify_finding(dict(text=text,classification='inference',evidence_ids=[calc['old_id'],calc['new_id']]),report,svc.store)
    assert verdict('City vacancy fell from 2026Q1 to 2026Q2; monitor whether this holds.')['status']=='verified'
    assert 'DIRECTION_CONTRADICTS_CALCULATION' in verdict('City vacancy rose from 2026Q1 to 2026Q2.')['reasons']


def test_positive_path_publishes_labelled_interpretation(svc):
    from london_product.chat_report import build_report, attach_analysis, render_markdown, render_html, read_report
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    content=dict(key_findings=[dict(text='City vacancy is 8 percent in 2026Q2; monitor.',classification='inference',evidence_ids=['v'])],
        risks=[dict(text='Further study could investigate City supply.',classification='scenario',evidence_ids=['v'])],
        opportunities=[],outlook=[])
    result=attach_analysis(svc.store,report['report_id'],content,run_id='offline-run')
    assert result['ai_analysis']['status']=='published'
    assert len(result['ai_analysis']['accepted'])==2 and not result['ai_analysis']['blocked']
    published=[f for f in result['key_findings']+result['risks'] if f.get('origin')=='model_interpretation']
    assert len(published)==2
    for f in published:
        assert f['verification']['status']=='verified' and f['verification']['origin']=='model_interpretation'
    assert result['generation_status']=='success'
    assert result['publication_review']['semantic_approval'] is False
    assert result['publication_review']['human_review_complete'] is False
    markdown=render_markdown(result)
    assert 'AI interpretation' in markdown and 'City vacancy is 8 percent' in markdown
    assert 'AI interpretation' in render_html(result)
    reopened=read_report(svc.store,result['report_id'])
    assert any(f.get('origin')=='model_interpretation' for f in reopened['key_findings'])


def test_mixed_batch_publishes_only_verified_findings(svc):
    from london_product.chat_report import build_report, attach_analysis
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    content=dict(key_findings=[dict(text='City vacancy is 8 percent in 2026Q2; monitor.',classification='inference',evidence_ids=['v'])],
        risks=[dict(text='Vacancy doubled to 99 percent.',classification='inference',evidence_ids=['v'])],
        opportunities=[dict(text='Demand caused rents to rise.',classification='inference',evidence_ids=['v'])],
        outlook=[dict(text='Coverage is fully approved across all metrics.',classification='scenario',evidence_ids=['v'])])
    result=attach_analysis(svc.store,report['report_id'],content)
    assert result['ai_analysis']['status']=='published'
    assert len(result['ai_analysis']['accepted'])==1
    assert len(result['ai_analysis']['blocked'])==3
    assert not result['opportunities'] and not any(f.get('origin')=='model_interpretation' for f in result['outlook'])
    assert len([f for f in result['risks'] if f.get('origin')=='model_interpretation'])==0


def test_chat_markdown_and_html_exports_are_consistent(svc):
    from london_product.chat_report import build_report, render_markdown, render_html
    observation(svc,'city')
    observation(svc,'west',geography='West End')
    query='Compare City and West End vacancy in Q2 2026'
    report=build_report(svc,query)
    markdown=render_markdown(report)
    html_out=render_html(report)
    for needle in ['Research scope','Regional Comparison','City','West End','vacant stock share','Sources & Evidence','Source last checked','Research scope','regional comparison']:
        assert needle in markdown, needle
    for needle in ['Research scope','Regional comparison','City','West End','Source last checked','Research scope','regional comparison','Observed period']:
        assert needle in html_out, needle
    chart=next(c for c in report['charts'] if c['type']=='regional_comparison')
    assert chart['status']=='ready' and len(chart['points'])==2
    assert '### vacancy · regional comparison [ready]' in markdown
    assert 'vacancy · regional comparison' in html_out
    for point in chart['points']:
        assert point['label'] in markdown and point['value'] in markdown
    assert 'Observed period: 2026Q2 · Published: 2026-07-01' in markdown
    assert 'Observed period: 2026Q2 / Publication: 2026-07-01' in html_out


def test_conflicting_observations_are_explained_never_averaged(svc):
    from london_product.chat_report import build_report, render_markdown, render_html
    observation(svc,'a',value='8')
    observation(svc,'b',value='9')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    assert report['conflicts']
    entry=report['conflicts'][0]
    assert {o['value'] for o in entry['observations']}=={'8','9'}
    markdown=render_markdown(report)
    assert 'Conflicting Observations — never averaged' in markdown
    assert '8 percent' in markdown and '9 percent' in markdown
    assert 'Conflicting observations — never averaged' in render_html(report)
    for chart in report['charts']:
        assert all('9' not in (p.get('value') or '') or '8' not in (p.get('value') or '') for p in chart['points'])


def test_followup_inherits_scope_without_promoting_parent_draft(svc):
    from london_product.chat_report import build_report, attach_analysis
    observation(svc,'v')
    parent=build_report(svc,'Analyse City vacancy Q2 2026')
    attach_analysis(svc.store,parent['report_id'],dict(key_findings=[dict(text='City vacancy is 8 percent in 2026Q2; monitor.',classification='inference',evidence_ids=['v'])]))
    child=build_report(svc,'What about availability?',parent_report_id=parent['report_id'])
    assert child['parent_report_id']==parent['report_id']
    assert child['scope']['geographies']==['City'] and child['scope']['observation_period']=='2026Q2'
    assert child['scope']['metrics']==['availability']
    assert all(f.get('origin')!='model_interpretation' for f in child['key_findings'])


def test_monitoring_loop_links_event_report_notification_and_dedupes(svc,monkeypatch):
    monkeypatch.delenv('LONDON_NOTIFICATION_URL',raising=False)
    observation(svc,'old',period='2026Q1',value='7')
    observation(svc,'new',period='2026Q2',value='9')
    result=svc.monitor_changes(run_id='offline-monitor',detection_context='historical_replay')
    assert result['alerts']==1
    event=svc.store.get('events',result['event_ids'][0])
    assert event['metric']=='vacancy' and event['comparison_id']
    assert 'HISTORICAL REPLAY' in event['importance_reason']
    assert 'System-computed change' in event['importance_reason']
    svc.save_settings({'notifications_enabled':True})
    outcomes=svc.monitor_intelligence(result,run_id='offline-monitor',detection_context='historical_replay')
    assert len(outcomes)==1 and not outcomes[0]['deduplicated']
    event=svc.store.get('events',event['id'])
    report=svc.store.get('reports',event['report_id'])
    assert report and report['artifact']['acquisition']['mode']=='scheduled_monitoring'
    assert 'Historical replay' in report['artifact']['acquisition']['notice']
    assert report['artifact']['generation_status']=='success'
    assert any(c['type']=='time_series' and c['status']=='ready' for c in report['artifact']['charts'])
    assert event['notification_status']=='configuration_missing'
    assert event['notification_id']
    second=svc.monitor_intelligence(result,run_id='offline-monitor',detection_context='historical_replay')
    assert second[0]['deduplicated'] and second[0]['report_id']==event['report_id']
    assert len(svc.store.all('notifications'))==1
    rerun=svc.monitor_changes(run_id='offline-monitor-2')
    assert rerun['event_ids']==result['event_ids']


def test_no_real_change_produces_no_alert_or_notification(svc):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value='8.1')
    result=svc.monitor_changes()
    assert result['alerts']==0 and not svc.monitor_intelligence(result)
    assert not svc.store.all('notifications')
