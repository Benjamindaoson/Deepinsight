"""Synthetic security regression inputs; never real market approval evidence."""
import pytest
from test_finding_verification import svc, observation
from london_product.chat_report import build_report,attach_analysis,read_report,render_markdown,render_html

NEGATIVE=[
 'City vacancy in 2026Q2 is zero.',
 'City vacancy in 2026Q2 is 8 hectares.',
 'City availability in 2026Q2 is 8 percent.',
 'City and West End vacancy in 2026Q2 was 8 percent.',
 'City and West End face severe flood damage.',
 'Every requested region has cleared all required checks and the dataset has no omissions.',
 'The City market was devastated by an earthquake.',
 'City vacancy is 8 percent in 2026Q2. All district offices were destroyed.',
 'Further study could investigate City demand because a catastrophic flood destroyed supply.',
 'City vacancy is 8 percent in 2026Q2; limited stock may warrant monitoring.',
]

@pytest.mark.parametrize('text',NEGATIVE)
def test_unbound_claim_never_persists_or_exports(svc,text):
 observation(svc,'v')
 report=build_report(svc,'Compare City and West End vacancy Q2 2026')
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text=text,classification='inference',evidence_ids=['v'])]))
 reopened=read_report(svc.store,result['report_id'])
 assert not any(f['text']==text for f in reopened['key_findings'])
 assert text not in render_markdown(reopened)
 assert text not in render_html(reopened)

def test_numbers_cannot_be_borrowed_across_metrics(svc):
 observation(svc,'v');observation(svc,'e',metric='employment',value='0',unit='people')
 report=build_report(svc,'Analyse City vacancy and employment Q2 2026')
 bad='City vacancy in 2026Q2 was 0 percent.'
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text=bad,classification='inference',evidence_ids=['v','e'])]))
 assert not result['ai_analysis']['accepted']

@pytest.mark.parametrize('text,kind',[
 ('City vacancy in 2026Q2 was 8 percent.','inference'),
 ('Further study could investigate City demand.','scenario'),
])
def test_supported_observation_and_research_action_publish(svc,text,kind):
 observation(svc,'v');report=build_report(svc,'Analyse City vacancy Q2 2026')
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text=text,classification=kind,evidence_ids=['v'])]))
 assert result['ai_analysis']['status']=='published'
 assert any(f['text']==text for f in read_report(svc.store,result['report_id'])['key_findings'])
 assert text in render_markdown(result) and text in render_html(result)

def typed_claim(row,**changes):
 return dict(kind='observation',metric=row['metric'],value=row['value'],unit=row['unit'],geography=row['geography'],
  observation_period=row['period'],definition=row['definition'],method=row['method'],evidence_ids=[row['id']],locator=row['evidence']['locator'],**changes)

def test_typed_tuple_and_text_have_independent_positive_checks(svc):
 from london_product.claim_binding import canonical
 row=observation(svc,'v');claim=typed_claim(row)
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text=canonical(claim),classification='inference',evidence_ids=['v'],claims=[claim])]))
 assert result['ai_analysis']['status']=='published'
 assert result['ai_analysis']['accepted'][0]['claims'][0]['metric']=='vacancy'
 reopened=read_report(svc.store,report['report_id'])
 assert any(f['origin']=='model_interpretation' for f in reopened['key_findings'])

@pytest.mark.parametrize('field,value',[('metric','availability'),('unit','hectares'),('value','0'),('geography','West End'),('observation_period','2026Q1'),('method','different'),('definition','different'),('locator','invented')])
def test_typed_field_mismatch_cannot_hide_behind_correct_prose(svc,field,value):
 from london_product.claim_binding import canonical
 row=observation(svc,'v');claim=typed_claim(row);correct=canonical(claim);claim[field]=value
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text=correct,classification='inference',evidence_ids=['v'],claims=[claim])]))
 assert not result['ai_analysis']['accepted']

def test_correct_typed_fields_cannot_authorize_false_prose(svc):
 row=observation(svc,'v');claim=typed_claim(row)
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(text='City vacancy is zero. Floods destroyed the district.',classification='inference',evidence_ids=['v'],claims=[claim])]))
 assert not result['ai_analysis']['accepted']

def test_old_unsafe_publication_is_rejected_on_reopen_without_database_mutation(svc):
 observation(svc,'v');report=build_report(svc,'Analyse City vacancy Q2 2026')
 bad='City vacancy is 8 hectares in 2026Q2.'
 report['key_findings'].append(dict(text=bad,classification='inference',evidence_ids=['v'],origin='model_interpretation',verification=dict(status='verified',verifier='finding-verifier-v1')))
 report['ai_analysis']=dict(status='published',accepted=[dict(text=bad)],blocked=[])
 svc.store.update('reports',report['report_id'],dict(artifact=report))
 reopened=read_report(svc.store,report['report_id'])
 assert bad not in render_markdown(reopened) and bad not in render_html(reopened)
 assert reopened['publication_review']['revalidation_rejections']
 assert svc.store.get('reports',report['report_id'])['artifact']['key_findings'][-1]['text']==bad

@pytest.mark.parametrize('with_report',[False,True])
def test_native_publication_projection_cannot_release_unbound_text(svc,with_report):
 import json
 from london_product.safe_answer import project_run
 row=observation(svc,'v');report=build_report(svc,'Analyse City vacancy Q2 2026')
 pack=dict(facts=[row],events=[])
 if with_report:pack['report_id']=report['report_id']
 bad='City and West End face severe flood damage.'
 run=dict(run_id='synthetic-native',agent_id='london-market-agent',status='COMPLETED',content=bad,
   tools=[dict(tool_name='search_market_evidence',result=json.dumps(pack))])
 assert bad not in project_run(run,svc.store)['answer']


def test_typed_change_with_digit_ids_publishes_and_reopens(svc):
 from london_product.claim_binding import _bound,canonical
 old=observation(svc,'old123',period='2026Q1',value='9')
 new=observation(svc,'new456',period='2026Q2',value='8')
 report=build_report(svc,'Analyse City vacancy Q2 2026 historical trend')
 claim=_bound(new,kind='change')
 claim.update(old_id=old['id'],new_id=new['id'],old_observation_period=old['period'],
   direction='decrease',evidence_ids=[old['id'],new['id']])
 text=canonical(claim)
 assert 'old123' not in text and 'new456' not in text
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(
   text=text,classification='inference',evidence_ids=claim['evidence_ids'],claims=[claim])]))
 assert result['ai_analysis']['status']=='published',result['ai_analysis']
 reopened=read_report(svc.store,report['report_id'])
 assert text in render_markdown(reopened) and text in render_html(reopened)


def test_fingerprint_invalidation_removes_outlook_from_every_delivery(svc):
 row=observation(svc,'v')
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 text='City vacancy in 2026Q2 was 8 percent.'
 result=attach_analysis(svc.store,report['report_id'],dict(outlook=[dict(
   text=text,classification='inference',evidence_ids=['v'])]))
 assert result['ai_analysis']['status']=='published'
 svc.store.update('facts','v',dict(grade='prime'))
 reopened=read_report(svc.store,report['report_id'])
 assert reopened['publication_review']['status']=='withheld'
 assert reopened['outlook']==[]
 assert text not in render_markdown(reopened) and text not in render_html(reopened)


@pytest.mark.parametrize('kind',['observation','source_statement','research_action'])
def test_typed_supported_kinds_publish_without_unused_fact_fields(svc,kind):
 from london_product.claim_binding import _bound,canonical
 row=observation(svc,'v')
 claim=_bound(row)
 classification='inference'
 if kind=='source_statement':claim.update(kind=kind,quote=row['evidence']['quote'])
 if kind=='research_action':
  claim=dict(kind=kind,geography='City',observation_period='2026Q2',evidence_ids=['v'],action='investigate_demand')
  classification='scenario'
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 content=dict(key_findings=[dict(text=canonical(claim),classification=classification,evidence_ids=['v'],claims=[claim])])
 result=attach_analysis(svc.store,report['report_id'],content)
 assert result['ai_analysis']['status']=='published',result['ai_analysis']
 # The same supported text cannot conceal an unused factual field.
 content['key_findings'][0]['claims'][0]['old_id']='invented'
 blocked=attach_analysis(svc.store,report['report_id'],content)
 assert not blocked['ai_analysis']['accepted']


def test_combined_requested_scope_accepts_exact_child_binding(svc):
 from london_product.claim_binding import _bound,canonical
 row=observation(svc,'mid',geography='Midtown')
 report=build_report(svc,'Analyse Midtown / Fringe vacancy Q2 2026')
 claim=_bound(row);text=canonical(claim)
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(
   text=text,classification='inference',evidence_ids=['mid'],claims=[claim])]))
 assert result['ai_analysis']['status']=='published',result['ai_analysis']
 # The row still cannot authorize a claim about the sibling submarket.
 claim['geography']='Fringe'
 blocked=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(
   text=canonical(claim),classification='inference',evidence_ids=['mid'],claims=[claim])]))
 assert not blocked['ai_analysis']['accepted']


def test_annualization_failure_does_not_relabel_existing_human_review(svc):
 row=observation(svc,'r',metric='rent',unit='GBP/sqft')
 report=build_report(svc,'Analyse City rent Q2 2026')
 text='A saved City rent observation is available; it remains pending human review.'
 result=attach_analysis(svc.store,report['report_id'],dict(key_findings=[dict(
   text=text,classification='inference',evidence_ids=['r'])]))
 assert not result['ai_analysis']['accepted']
 assert svc.store.get('facts','r')['human_review_status']=='approved'
 assert text not in render_markdown(read_report(svc.store,report['report_id']))
