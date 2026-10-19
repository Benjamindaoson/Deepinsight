import copy
import pytest
from test_chat_report import svc, observation
from london_product.chat_report import build_report, attach_analysis, read_report


def market(svc):
    for geo, values in [('City', ['9.8', '9.4', '1000000', '1100000']), ('West End', ['6.8', '6.7', '810000', '1000000'])]:
        for metric, pair in [('vacancy', values[:2]), ('takeup', values[2:])]:
            for period, value in zip(['2026Q1', '2026Q2'], pair):
                identity = geo + metric + period
                observation(svc, identity, geography=geo, metric=metric, period=period, value=value,
                    unit='percent' if metric == 'vacancy' else 'sqft')
                if metric == 'takeup':svc.store.update('facts', identity, dict(basis='quarter'))
    return build_report(svc, 'Prepare Q2 2026 market report comparing City, West End and Canary Wharf vacancy and leasing take-up with historical trends, risks and opportunities')


def test_partial_regional_chart_lists_only_observed_areas(svc):
    report = market(svc)
    charts = [c for c in report['charts'] if c['type'] == 'regional_comparison' and c['status'] == 'ready']
    assert charts
    assert all(set(c['geographies']) == {p['geography'] for p in c['points']} == {'City', 'West End'} for c in charts)
    assert report['generation_status'] == 'partial'
    assert any(g['geography'] == 'Canary Wharf' for g in report['data_gaps'])


def choices(report, store):
    from london_product.conditional_analysis import analysis_choices
    return analysis_choices(report, store)


def test_compact_model_choices_publish_comparison_risk_and_opportunity(svc):
    report = market(svc); candidates = choices(report, svc.store)
    payload = {category: [dict(candidate_id=next(c['candidate_id'] for c in candidates if category in c['categories']))]
        for category in ['key_findings', 'risks', 'opportunities']}
    import json
    assert len(json.dumps(payload).encode()) < 500
    result = attach_analysis(svc.store, report['report_id'], payload)
    assert result['ai_analysis']['status'] == 'published'
    assert len(result['ai_analysis']['accepted']) == 3 and not result['ai_analysis']['blocked']
    assert 'conditional risk' in result['risks'][0]['text']
    assert 'not an investment recommendation' in result['opportunities'][0]['text']
    assert 'higher than' in next(f['text'] for f in result['key_findings'] if f.get('origin') == 'model_interpretation')
    assert len(result['risks'][0]['evidence_ids']) == 4
    reopened = read_report(svc.store, report['report_id'])
    assert reopened['ai_analysis']['status'] == 'published'
    assert reopened['ai_analysis']['semantic_approval'] is False


@pytest.mark.parametrize('mutation', ['pending', 'opposite', 'period', 'source', 'definition', 'method', 'tamper'])
def test_invalidated_scenario_never_released(svc, mutation):
    report = market(svc)
    candidate = next(c for c in choices(report, svc.store) if 'risks' in c['categories'])
    fid = candidate['finding']['claims'][0]['takeup_new_id']
    patch = {'pending': dict(human_review_status='pending_review'), 'opposite': dict(value='1'),
        'period': dict(period='2025Q4'), 'source': dict(source_id='other'),
        'definition': dict(definition='different definition'), 'method': dict(method='unknown')}
    if mutation == 'tamper':
        from pathlib import Path
        doc = svc.store.get('documents', svc.store.get('facts', fid)['document_id'])
        Path(doc['path']).write_bytes(b'changed source')
    else:svc.store.update('facts', fid, patch[mutation])
    result = attach_analysis(svc.store, report['report_id'], dict(risks=[dict(candidate_id=candidate['candidate_id'])]))
    assert not result['ai_analysis']['accepted'] and not result['risks']


@pytest.mark.parametrize('selection', [dict(candidate_id='invented'), dict(candidate_id='valid', text='Guaranteed profit.'), dict(candidate_id='valid', claims=[])])
def test_choice_does_not_authorize_extra_model_prose(svc, selection):
    report = market(svc); candidate = next(c for c in choices(report, svc.store) if 'risks' in c['categories'])
    selection = copy.deepcopy(selection)
    if selection['candidate_id'] == 'valid':selection['candidate_id'] = candidate['candidate_id']
    result = attach_analysis(svc.store, report['report_id'], dict(risks=[selection]))
    assert not result['ai_analysis']['accepted']


def test_opportunity_cannot_be_relabelled_as_risk(svc):
    report = market(svc); candidate = next(c for c in choices(report, svc.store) if 'opportunities' in c['categories'])
    result = attach_analysis(svc.store, report['report_id'], dict(risks=[dict(candidate_id=candidate['candidate_id'])]))
    assert not result['ai_analysis']['accepted']


def test_published_conditional_is_withheld_after_review_revocation(svc):
    report = market(svc); candidate = next(c for c in choices(report, svc.store) if 'risks' in c['categories'])
    result = attach_analysis(svc.store, report['report_id'], dict(risks=[dict(candidate_id=candidate['candidate_id'])]))
    assert result['risks']
    svc.review_fact(result['risks'][0]['evidence_ids'][0], 'reopen', 'test-reviewer', 'Recheck original definition')
    reopened = read_report(svc.store, report['report_id'])
    assert not reopened['risks'] and reopened['publication_review']['status'] == 'withheld'


def test_native_tool_offers_small_choices_for_all_three_sections(svc):
    import json
    from agno.db.sqlite import SqliteDb
    from agno.run import RunContext
    from london_product.intelligence import query_agent
    from london_product.chat_report import ACTIVE_REPORT
    report = market(svc)
    agent = query_agent(svc, SqliteDb(db_file=str(svc.store.root / 'native.sqlite3')))
    loader = next(t for t in agent.tools if getattr(t, 'name', None) == 'load_market_skills')
    tool = next(t for t in agent.tools if getattr(t, 'name', None) == 'search_market_evidence')
    context = RunContext(run_id='offline-contract', session_id='offline', session_state={})
    loader.entrypoint(run_context=context, skill_names=['market-intelligence'])
    token = ACTIVE_REPORT.set(report['report_id'])
    try:
        raw = tool.entrypoint(run_context=context, query=report['query'])
    finally:ACTIVE_REPORT.reset(token)
    assert len(raw.encode()) <= 10000
    contract = json.loads(raw)['analysis_contract']
    sections = {c['section'] for c in contract['candidate_choices']}
    assert {'key_findings', 'risks', 'opportunities'} <= sections
    assert contract['selection_format'] == {'candidate_id': 'copy one supplied ID only'}


def test_real_change_report_includes_evidence_cross_checks_without_changing_threshold(svc):
    market(svc)
    svc.save_settings(dict(geographies=['West End'], monitor_analysis_enabled=False, notifications_enabled=False))
    result = svc.monitor_changes(detection_context='historical_replay')
    assert result['alerts'] == 1 and svc.settings()['takeup_threshold_pct'] == 10
    outcomes = svc.monitor_intelligence(result, detection_context='historical_replay')
    report = read_report(svc.store, outcomes[0]['report_id'])
    assert {'takeup', 'vacancy'} <= set(report['scope']['metrics'])
    assert report['acquisition']['detection_context'] == 'historical_replay'
    assert any('risks' in c['categories'] for c in choices(report, svc.store))


def test_mixed_sign_typed_changes_are_checked_per_pair(svc):
    from london_product.claim_binding import canonical, _bound
    report = market(svc); claims = [];ids = []
    for metric in ['takeup', 'vacancy']:
        old = svc.store.get('facts', 'West End' + metric + '2026Q1')
        new = svc.store.get('facts', 'West End' + metric + '2026Q2')
        claim = _bound(new, kind='change', old_id=old['id'], new_id=new['id'], old_observation_period='2026Q1', direction='increase' if metric == 'takeup' else 'decrease')
        claim['evidence_ids'] = [old['id'], new['id']];claims.append(claim);ids.extend(claim['evidence_ids'])
    finding = dict(text=' '.join(canonical(c) for c in claims), classification='inference', evidence_ids=ids, claims=claims)
    result = attach_analysis(svc.store, report['report_id'], dict(key_findings=[finding]))
    assert result['ai_analysis']['status'] == 'published'
    bad = copy.deepcopy(finding);bad['claims'][1]['direction'] = 'increase'
    bad['text'] = ' '.join(canonical(c) for c in bad['claims'])
    result = attach_analysis(svc.store, report['report_id'], dict(key_findings=[bad]))
    assert not result['ai_analysis']['accepted']


def test_forged_saved_calculation_cannot_reverse_a_real_direction(svc):
    from london_product.claim_binding import canonical, _bound
    report=market(svc)
    calc=next(c for c in report['calculations'] if c['new_id']=='West Endvacancy2026Q2')
    calc['absolute_change']='1';calc['relative_change_pct']='11.11'
    svc.store.update('reports',report['report_id'],dict(artifact=report))
    catalog=choices(report,svc.store)
    assert not any(c['finding']['claims'][0].get('new_id')==calc['new_id'] for c in catalog)
    row=svc.store.get('facts',calc['new_id'])
    claim=_bound(row,kind='change',old_id=calc['old_id'],new_id=calc['new_id'],old_observation_period='2026Q1',direction='increase')
    claim['evidence_ids']=[calc['old_id'],calc['new_id']]
    finding=dict(text=canonical(claim),classification='inference',evidence_ids=claim['evidence_ids'],claims=[claim])
    result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[finding]))
    assert not result['ai_analysis']['accepted']
    reopened=read_report(svc.store,report['report_id'])
    assert reopened['publication_review']['status']=='withheld'
    assert all(c['status']!='ready' for c in reopened['charts'])


@pytest.mark.parametrize('field', ['display','geography','period','snapshot'])
def test_cached_calculation_presentation_cannot_override_sources(svc,field):
    report=market(svc)
    calc=next(c for c in report['calculations'] if c['new_id']=='West Endvacancy2026Q2')
    if field=='display':calc['display']['absolute_change']='1.00'
    elif field=='geography':calc['geography']='Canary Wharf'
    elif field=='period':calc['new_period']='2027Q1'
    else:calc['new']['value']='99'
    svc.store.update('reports',report['report_id'],dict(artifact=report))
    reopened=read_report(svc.store,report['report_id'])
    assert reopened['publication_review']['status']=='withheld'
    assert not reopened['calculations']
