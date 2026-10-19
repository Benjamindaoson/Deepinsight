import pytest
from london_product.chat_report import resolve_scope,respond_to_action,build_report
from london_product.service import MarketService
from london_product.store import Store
from london_product.routing import request_action


def test_negated_metric_and_explicit_month_and_future_scope():
    assert resolve_scope('Explain City office rent trends. Do not substitute vacancy data for rent evidence.')['metrics']==['rent']
    assert resolve_scope('What changed during September 2026? Use September observations, not quarterly substitutes.')['observation_period']=='2026-09'
    assert resolve_scope('What is the guaranteed West End prime rent in 2027?')['observation_period']=='2027'
    assert resolve_scope('What is the latest Bank of England Bank Rate?')['metrics']==['interest_rate']
    assert resolve_scope('Is flight to quality increasing in London offices?')['metrics']==['flight_to_quality']
    assert request_action('Explain City office rent trends. Do not substitute vacancy data for rent evidence.')=='model_analysis'


@pytest.mark.parametrize('question,operation',[
    ('Audit the evidence supporting the report you just generated.','evidence_audit'),
    ('Which exact source supports the West End vacancy figure in the previous answer?','follow_up'),
    ('How does that compare with the West End?','data_question'),
    ('What is the guaranteed prime office rent in 2027?','future_uncertainty'),
    ('How are London office rents?','clarification'),
    ('Write me a chocolate cake recipe.','out_of_domain'),
    ('Schedule a briefing every Monday at 09:00 Europe/London.','schedule_request'),
    ('Monitor City prime office rents monthly and alert me when the increase exceeds 2%.','monitor_rule'),
])
def test_operational_intents(question,operation):
    assert request_action(question,has_context=True)==operation


def test_audit_lists_exact_claims_not_just_observations(tmp_path):
    service=MarketService(Store(tmp_path))
    report=build_report(service,'City office market report Q2 2026')
    row=service.store.get('reports',report['report_id'])
    artifact=row['artifact'];artifact['key_findings']=[dict(text='City rent is guaranteed to double.',classification='inference',evidence_ids=['missing'])]
    service.store.update('reports',row['id'],dict(artifact=artifact))
    count=len(service.store.all('reports'))
    result=respond_to_action(service,'Audit every unsupported claim in this report.',row['id'])
    assert 'City rent is guaranteed to double.' in result['answer']
    assert 'Unsupported' in result['answer'] or 'Unverified' in result['answer']
    assert '|\n|---' in result['answer']
    assert len(service.store.all('reports'))==count
    service.pool.shutdown()


def test_waiting_monthly_rule_is_persisted_and_visible_in_existing_settings(tmp_path):
    service=MarketService(Store(tmp_path))
    result=respond_to_action(service,'Monitor City prime office rents monthly and alert me above 2%.')
    rule=service.settings()['monitoring_rules'][0]
    assert rule['id']==result['rule_id']
    assert rule['rule']['active'] is False
    assert rule['rule']['period']=='monthly'
    assert rule['rule']['operator']=='strictly_greater_than'
    service.pool.shutdown()
