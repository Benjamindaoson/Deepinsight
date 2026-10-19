"""A user's explicit two-quarter comparison must retain both saved periods."""
import pytest
from test_chat_report import svc, observation
from london_product.chat_report import resolve_scope, build_report

@pytest.mark.parametrize('query', [
    'Compare West End vacancy in Q1 and Q2 2026',
    'Compare West End vacancy in Q2 2026 and Q1 2026',
    'Compare West End vacancy in 2026Q1 and 2026Q2',
    'Compare West End vacancy in Q4 2025 and Q1 2026',
])
def test_explicit_period_pair_sets_history_and_latest_endpoint(query):
    scope=resolve_scope(query)
    assert scope['needs_history'] is True
    assert scope['observation_period']==('2026Q1' if '2025' in query else '2026Q2')

def test_single_period_cross_area_comparison_does_not_request_history():
    scope=resolve_scope('Compare City and West End vacancy in Q2 2026')
    assert scope['needs_comparison'] and not scope['needs_history']

def test_explicit_two_period_request_reaches_real_comparison_and_persistence(svc):
    observation(svc,'q1',geography='West End',period='2026Q1',value='6.8')
    observation(svc,'q2',geography='West End',period='2026Q2',value='6.7')
    result=build_report(svc,'Compare West End overall vacancy in Q1 and Q2 2026')
    assert result['scope']['needs_history']
    assert result['calculations'][0]['absolute_change']=='-0.1'
    assert result['calculations'][0]['change_unit']=='pp'
    assert any(c['status']=='ready' and c['type']=='time_series' for c in result['charts'])
    saved=svc.store.get('reports',result['report_id'])['artifact']
    assert {e['period'] for e in saved['evidence']}=={'2026Q1','2026Q2'}

def test_missing_requested_quarter_is_not_replaced_by_an_unrequested_quarter(svc):
    observation(svc,'q2',period='2026Q2',value='8')
    observation(svc,'q3',period='2026Q3',value='7')
    result=build_report(svc,'Compare City vacancy in Q1 2026 and Q3 2026')
    assert result['scope']['requested_periods']==['2026Q1','2026Q3']
    assert not result['calculations']
    assert any(g['component']=='history' for g in result['data_gaps'])
    assert result['generation_status']!='success'

def test_one_ready_pair_does_not_hide_another_explicitly_requested_missing_period(svc):
    observation(svc,'q2',period='2026Q2',value='8')
    observation(svc,'q3',period='2026Q3',value='7')
    result=build_report(svc,'Compare City vacancy Q1 2026, Q2 2026 and Q3 2026')
    assert any(c['status']=='ready' for c in result['charts'])
    assert any('2026Q1' in g.get('missing_periods',[]) for g in result['data_gaps'])
    assert result['generation_status']=='partial'

def test_one_ready_pair_does_not_hide_an_incompatible_requested_pair(svc):
    observation(svc,'q1',period='2026Q1',value='9',definition='different sample definition')
    observation(svc,'q2',period='2026Q2',value='8')
    observation(svc,'q3',period='2026Q3',value='7')
    result=build_report(svc,'Compare City vacancy Q1 2026, Q2 2026 and Q3 2026')
    assert any(c['status']=='ready' for c in result['charts'])
    assert result['generation_status']=='partial'
    assert any(['2026Q1','2026Q2'] in g.get('missing_comparisons',[]) for g in result['data_gaps'])
