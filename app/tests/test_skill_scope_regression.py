"""Offline regressions for real-browser question scope and report selection."""
import pytest

from london_product.chat_report import build_report, resolve_scope
from test_chat_report import observation, svc


A_QUESTION = (
    '请根据系统现有的伦敦办公地产市场资料，汇总目前可以核验的市场指标。'
    '对每项指标列出数值、单位、统计期间、地域、发布机构、原文出处和审核状态。'
    '没有可靠证据的指标请明确标记为未知，不要推测。'
)


@pytest.mark.parametrize('question', [
    A_QUESTION,
    'Summarize all verifiable London office market indicators from saved evidence.',
    '列出伦敦办公市场现有资料中每项市场指标及证据状态。',
])
def test_a_indicator_inventory_covers_submarkets_and_multiple_metrics(question):
    scope = resolve_scope(question)
    assert {'City', 'West End', 'Canary Wharf', 'Central London',
            'United Kingdom', 'London (workplace)'} <= set(scope['geographies'])
    assert {'rent', 'vacancy', 'availability', 'takeup', 'supply',
            'interest_rate', 'employment', 'inflation_rate'} <= set(scope['metrics'])


def test_a_inventory_selects_approved_submarket_evidence_and_keeps_unknowns(svc):
    observation(svc, 'west-vacancy', geography='West End')
    result = build_report(svc, A_QUESTION)
    assert any(row['fact_id'] == 'west-vacancy' and row['review_status'] == 'approved'
               for row in result['market_snapshot'])
    assert any(gap['metric'] == 'rent' for gap in result['data_gaps'])
    assert result['generation_status'] != 'success'


def test_inventory_words_do_not_override_explicit_area_or_metric():
    scope = resolve_scope('Summarize all verified West End market indicators for vacancy in Q2 2026')
    assert scope['geographies'] == ['West End']
    assert scope['metrics'] == ['vacancy']
    assert scope['observation_period'] == '2026Q2'


def test_b_explicit_west_end_two_quarters_remains_narrow():
    scope = resolve_scope('请比较West End在2026年第一季度和2026年第二季度的空置率。')
    assert scope['geographies'] == ['West End']
    assert scope['metrics'] == ['vacancy']
    assert scope['requested_periods'] == ['2026Q1', '2026Q2']
    assert scope['needs_history'] is True


@pytest.mark.parametrize('month', ['2026年10月', 'October 2026', '2026-10'])
def test_c_exact_canary_wharf_month_never_selects_latest_quarter(svc, month):
    observation(svc, 'quarter-only', geography='Canary Wharf', period='2026Q2')
    result = build_report(svc, f'请核验Canary Wharf在{month}的空置率。')
    assert result['scope']['geographies'] == ['Canary Wharf']
    assert result['scope']['observation_period'] == '2026-10'
    assert result['scope']['requested_periods'] == ['2026-10']
    assert result['market_snapshot'] == []
    assert any(gap['period'] == '2026-10' for gap in result['data_gaps'])


def test_f_follow_up_retains_parent_area_metrics_and_requested_periods(svc):
    for identity, period in [('q1', '2026Q1'), ('q2', '2026Q2')]:
        observation(svc, identity, geography='West End', period=period)
    parent = build_report(svc, 'Compare West End vacancy in Q1 and Q2 2026')
    follow = build_report(svc, '请继续核验这些结论的证据和审核状态。', parent['report_id'])
    assert follow['scope']['geographies'] == ['West End']
    assert follow['scope']['metrics'] == ['vacancy']
    assert follow['scope']['requested_periods'] == ['2026Q1', '2026Q2']
    assert follow['scope']['needs_history'] is True
    assert {row['period'] for row in follow['evidence']} == {'2026Q1', '2026Q2'}


def test_follow_up_period_override_does_not_keep_stale_parent_periods():
    parent = resolve_scope('Compare West End vacancy in Q1 and Q2 2026')
    assert resolve_scope('What about Q3?', parent)['observation_period'] == '2026Q3'
    latest = resolve_scope('Use latest evidence', parent)
    assert latest['observation_period'] is None
    assert latest['requested_periods'] == []


def test_d_chinese_causal_question_preserves_office_and_macro_scope():
    scope = resolve_scope(
        '现有资料能够证明英国利率、就业变化或混合办公趋势已经导致伦敦办公租金变化吗？'
        '请区分直接观测到的事实、可能的解释和目前无法证明的因果关系，并逐条列出证据。'
    )
    assert scope['metrics'] == ['rent', 'interest_rate', 'employment', 'hybrid_working']
    assert set(scope['geographies']) == {'Central London', 'United Kingdom', 'London (workplace)'}


def test_mixed_macro_scope_preserves_explicit_office_area_and_publisher_labels(svc):
    observation(svc, 'office', geography='City', metric='rent', unit='GBP/sqft/year')
    observation(svc, 'bank', geography='United Kingdom', metric='interest_rate',
                definition='Bank Rate', unit='percent')
    observation(svc, 'jobs', geography='London (workplace)', metric='employment',
                definition='Workforce jobs', unit='jobs')
    result = build_report(svc, 'Analyse City office rent, UK interest rates and London employment in Q2 2026')
    assert result['scope']['geographies'] == ['City', 'United Kingdom', 'London (workplace)']
    evidence = {row['id']: row['geography'] for row in result['evidence']}
    assert evidence == {'office': 'City', 'bank': 'United Kingdom', 'jobs': 'London (workplace)'}


def test_macro_context_does_not_expand_an_office_only_question():
    scope = resolve_scope('Analyse West End rent and hybrid working in Q2 2026')
    assert scope['geographies'] == ['West End']
    assert scope['metrics'] == ['rent', 'hybrid_working']


E_QUESTION = (
    '请从系统已经保存并且能够核验来源的新闻或机构披露中，选择一项与伦敦办公市场有关的事件，'
    '说明发生了什么、可能影响哪些子市场、有哪些证据支持这些判断，以及哪些内容仍然属于推测。'
)


@pytest.mark.parametrize('question', [E_QUESTION,
    'Choose one saved news event relevant to London offices and explain the evidence.',
    'Select one institutional disclosure about an event affecting the London office market.',
])
def test_e_saved_event_inquiry_has_event_scope_without_default_rent(question):
    scope = resolve_scope(question)
    assert scope['report_type'] == 'topic_analysis'
    assert scope['metrics'] == []
    assert {'City', 'West End', 'Canary Wharf', 'Central London', 'London'} <= set(scope['geographies'])


def test_event_scope_keeps_explicit_area_period_and_metric():
    scope = resolve_scope('Explain saved West End news events affecting rent in Q2 2026')
    assert scope['geographies'] == ['West End']
    assert scope['metrics'] == ['rent']
    assert scope['observation_period'] == '2026Q2'
    assert scope['report_type'] == 'topic_analysis'


def test_e_source_native_london_event_reaches_evidence_and_timeline(svc):
    original = observation(svc, 'source-document', geography='London')
    svc.store.put('events', 'saved-event', dict(
        id='saved-event', title='Saved institutional disclosure', source_id='official',
        document_id=original['document_id'], geography='London', event_date='2026-05-02',
        published_at='2026-05-03', status='pending_review', evidence=original['evidence']))
    result = build_report(svc, E_QUESTION)
    assert result['scope']['metrics'] == []
    assert result['market_snapshot'] == []
    assert {row['id'] for row in result['evidence']} == {'saved-event'}
    timeline = next(chart for chart in result['charts'] if chart['type'] == 'event_timeline')
    assert timeline['status'] == 'ready'
    assert timeline['points'][0]['geography'] == 'London'
    assert timeline['points'][0]['evidence_ids'] == ['saved-event']
def test_explicit_only_scope_excludes_geography_in_source_title():
    from london_product.chat_report import resolve_scope
    chinese=resolve_scope('请核对附件 BNP Central London Q2 2026 原始报告，只分析 West End 的 overall vacancy。列出审核状态。')
    english=resolve_scope('Read the Central London Q2 2026 source. Only analyze West End overall vacancy.')
    assert chinese['geographies']==['West End']
    assert english['geographies']==['West End']


def test_explicit_scope_can_keep_two_requested_submarkets():
    from london_product.chat_report import resolve_scope
    scope=resolve_scope('附件 Central London Q2 2026；仅针对 West End 和 City 分析 vacancy。',
        {'geographies':['Canary Wharf'],'metrics':['vacancy']})
    assert set(scope['geographies'])=={'West End','City'}


@pytest.mark.parametrize('question',[
    'Only analyze City, West End and Canary Wharf rents in 2026Q2.',
    '仅分析 City，West End、Canary Wharf 在2026Q2的租金。',
])
def test_restricted_scope_preserves_comma_separated_market_list(question):
    scope=resolve_scope(question)
    assert set(scope['geographies'])=={'City','West End','Canary Wharf'}
    assert scope['needs_comparison'] is True


def test_restricted_scope_does_not_import_publisher_after_comma():
    scope=resolve_scope('Only analyze West End vacancy, using the Central London report in 2026Q2.')
    assert scope['geographies']==['West End']
