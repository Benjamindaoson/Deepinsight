"""SYNTHETIC state faults; no real market approval or model request."""
import json
import pytest
from agno.run import RunContext
from agno.db.sqlite import SqliteDb
from fastapi.testclient import TestClient
from types import SimpleNamespace
from test_finding_verification import svc, observation
from london_product.chat_report import build_report,attach_analysis,read_report,render_markdown,render_html

CASES=[
 ('All requested regions have approved observations.','STATE_APPROVAL_CONTRADICTION'),
 ('There is complete coverage across all requested regions and indicators.','STATE_COVERAGE_CONTRADICTION'),
 ('There are no saved City vacancy observations.','STATE_EXISTENCE_CONTRADICTION'),
 ('Independent semantic review has approved all findings.','STATE_SEMANTIC_APPROVAL_CONTRADICTION'),
]


@pytest.mark.parametrize('text,reason',CASES)
def test_contradictions_are_explained_against_authority_and_audited(svc,text,reason):
    observation(svc,'city')
    observation(svc,'west',geography='West End',approved=False)
    report=build_report(svc,'Compare City and West End rent and vacancy Q2 2026')
    payload=dict(outlook=[dict(text=text,classification='inference',evidence_ids=['city'])])
    result=attach_analysis(svc.store,report['report_id'],payload,run_id='SYNTHETIC-state')
    assert reason in result['ai_analysis']['blocked'][0]['reason']
    audit=result['ai_analysis']['validation_audit'][0]
    assert audit['original_text']==text and audit['evidence_ids']==['city']
    assert audit['verification']['state_checks'] and audit['outcome']=='rejected'
    assert result['ai_analysis']['original_payload']==payload
    assert text not in render_markdown(read_report(svc.store,report['report_id']))
    assert text not in render_html(read_report(svc.store,report['report_id']))
    assert result['publication_review']['semantic_approval'] is False
    assert result['market_snapshot']==report['market_snapshot']


def test_supported_local_approval_publishes_without_approving_other_regions(svc):
    observation(svc,'city');observation(svc,'west',geography='West End',approved=False)
    report=build_report(svc,'Compare City and West End vacancy Q2 2026')
    text='A reviewed City vacancy observation is available; broader market conclusions require additional evidence.'
    result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(text=text,classification='inference',evidence_ids=['city'])]))
    assert result['ai_analysis']['status']=='published'
    assert text in render_markdown(read_report(svc.store,report['report_id']))
    assert text in render_html(read_report(svc.store,report['report_id']))
    assert result['ai_analysis']['accepted'][0]['claims'][0]['kind']=='state_assertion'
    assert svc.store.get('facts','west')['human_review_status']=='pending_review'


def test_saved_pending_status_can_publish_but_market_inference_cannot(svc):
    observation(svc,'city',approved=False)
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    status='A saved City vacancy observation is available; it remains pending human review.'
    result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[
        dict(text=status,classification='inference',evidence_ids=['city']),
        dict(text='City vacancy in 2026Q2 was 8 percent.',classification='inference',evidence_ids=['city'])]))
    assert result['ai_analysis']['status']=='published'
    assert [f['text'] for f in result['ai_analysis']['accepted']]==[status]
    assert svc.store.get('facts','city')['human_review_status']=='pending_review'


def test_state_scope_is_not_inferred_from_another_quarter_or_combined_area(svc):
    observation(svc,'city-old',period='2026Q1')
    observation(svc,'combined',geography='Canary Wharf & Docklands')
    report=build_report(svc,'Compare City and Canary Wharf vacancy Q2 2026')
    result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(
        text='All requested regions have approved observations.',classification='inference',evidence_ids=['combined'])]))
    assert not result['ai_analysis']['accepted']
    assert 'STATE_APPROVAL_CONTRADICTION' in result['ai_analysis']['blocked'][0]['reason']


def test_coverage_and_approval_checks_have_a_positive_control(svc):
    observation(svc,'city');observation(svc,'west',geography='West End')
    report=build_report(svc,'Compare City and West End vacancy Q2 2026')
    result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(text=text,classification='inference',evidence_ids=['city','west']) for text,_ in CASES[:2]]))
    assert len(result['ai_analysis']['accepted'])==2
    assert all(v['outcome']=='accepted' for v in result['ai_analysis']['validation_audit'])


def test_approval_labels_do_not_override_report_metadata_eligibility(svc):
    observation(svc,'city',definition=None)
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    assert report['market_snapshot'][0]['review_status']=='pending_review'
    for text,_ in CASES[:2]:
        result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(text=text,classification='inference',evidence_ids=['city'])]))
        assert not result['ai_analysis']['accepted']
        assert 'CONTRADICTION' in result['ai_analysis']['blocked'][0]['reason']


def test_malformed_unrelated_observation_is_audited_without_crashing_state_check(svc):
    observation(svc,'good',metric='rent',unit='GBP/sqft/year')
    observation(svc,'bad',metric='rent',unit='GBP/sqft/year',value='not supplied',approved=False)
    report=build_report(svc,'Analyse City rent Q2 2026')
    result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(
        text='A saved City rent observation is available.',classification='inference',evidence_ids=['good'])]))
    assert result['ai_analysis']['status']=='published'
    check=result['ai_analysis']['validation_audit'][0]['verification']['state_checks'][0]
    assert any(row['id']=='bad' for row in check['excluded'])


@pytest.mark.parametrize('text,reason',CASES+[(
    'A reviewed City vacancy observation is available; broader market conclusions require additional evidence.',None)])
def test_runtime_calls_same_state_gate_before_report_publication(tmp_path,text,reason):
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False)
    observation(app.state.market,'city');observation(app.state.market,'west',geography='West End',approved=False)
    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))
        async def arun(self,*args,**kwargs):
            yield SimpleNamespace(event='ToolCallCompleted',run_id='SYNTHETIC',tool=SimpleNamespace(
                tool_name='load_market_skills',tool_call_error=False,result=json.dumps({'audit_id':'synthetic-skill-load'})))
            yield SimpleNamespace(event='ToolCallCompleted',run_id='SYNTHETIC',tool=SimpleNamespace(
                tool_name='search_market_evidence',tool_call_error=False,result=json.dumps({'facts':[],'events':[],'documents':{}})))
            yield SimpleNamespace(event='RunContent',run_id='SYNTHETIC',content=json.dumps(dict(outlook=[dict(text=text,classification='inference',evidence_ids=['city'])])))
            yield SimpleNamespace(event='RunCompleted',run_id='SYNTHETIC')
    app.state.market.agent_factory=OfflineAgent
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json=dict(message='Compare City and West End rent and vacancy Q2 2026',mode='agent'))
        events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        report=next(e['report'] for e in reversed(events) if e['type']=='report')
        if reason:assert reason in report['ai_analysis']['blocked'][0]['reason']
        else:assert report['ai_analysis']['status']=='published'
        delivered=''.join(e['content'] for e in events if e['type']=='token')
        if reason:assert text not in delivered
        else:assert text in delivered

@pytest.mark.parametrize('case,accepted', [('missing',False),('complete',True),('substituted',False),('definition_conflict',False)])
def test_complete_coverage_binds_every_requested_period_and_comparability(svc,case,accepted):
    observation(svc,'q2',period='2026Q2',value='6.7')
    if case!='missing':
        observation(svc,'old',period='2025Q4' if case=='substituted' else '2026Q1',value='6.8',
            definition='incompatible availability definition' if case=='definition_conflict' else 'vacant stock share')
    report=build_report(svc,'Compare City vacancy in Q1 2026 and Q2 2026')
    ids=[e['id'] for e in report['evidence']]
    text='There is complete coverage across all requested regions and indicators.'
    result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(text=text,classification='inference',evidence_ids=ids)]))
    assert bool(result['ai_analysis']['accepted']) is accepted
    if not accepted:
        assert 'STATE_COVERAGE_CONTRADICTION' in result['ai_analysis']['blocked'][0]['reason']
        assert text not in render_markdown(read_report(svc.store,report['report_id']))
