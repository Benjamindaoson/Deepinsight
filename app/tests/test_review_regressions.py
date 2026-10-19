"""Synthetic adversarial and failure sequences from the independent final review."""
import json
import time
import pytest
from test_foundation import fact
from london_data.validation import validate
from london_data.store import Repository
from london_data.comparison import compare
from london_data.extraction import Budget, BoundedOpenAIChat
from agno.models.openai import OpenAIChat


@pytest.mark.parametrize('quote,value',[
    ('Central London vacancy rate was 8.4%','8.4'),
    ('Central London take-up in Q4 2025 was 3.0m sq ft','3000000'),
    ('Central London YTD take-up in Q1 2026 was 3.0m sq ft','3000000'),
    ('Central London take-up was 2.0m sq ft in Q1 2026; YTD total was 3.0m sq ft','3000000'),
])
def test_wrong_metric_period_or_flow_binding_is_rejected(quote,value):
    f=fact(metric='takeup',geography='Central London',value=value,unit='sqft',basis='quarter',currency=None,
           precision='0.1' if value=='8.4' else '100000',evidence={'segment_id':'p3','quote':quote})
    assert validate(f,[{'segment_id':'p3','text':quote}],expected_period='2026Q1')['status']=='needs_review'


def test_conflict_invalidates_current_comparison_but_keeps_history(tmp_path):
    s=Repository(tmp_path/'r.db')
    a=s.attempt('d1','v1','r1');s.persist(a,[fact(value='100'),fact(value='110',period='2026Q2',document_id='d2')])
    old,new=s.observations();first=s.save_comparison(compare(old,new))
    a=s.attempt('d3','v1','r2');s.persist(a,[fact(value='120',period='2026Q2',document_id='d3')])
    assert not any(c['status']=='comparable' for c in s.current_comparisons())
    updated={o['id']:o for o in s.observations(include_all=True)}
    second=s.save_comparison(compare(updated[old['id']],updated[new['id']]))
    assert second['status']=='not_comparable' and second['id']!=first['id']
    assert s.get('comparisons',first['id'])['status']=='comparable'


def test_fixed_result_id_and_unknown_id_do_not_fall_back(tmp_path,monkeypatch):
    from london_data import runtime
    s=Repository(tmp_path/'id.db');a=s.attempt('d','v1','r')
    d=s.snapshot('bnp','https://example.org/report',b'x','text/html',None,[])
    s.persist(a,[fact(document_id=d['id']),fact(period='2026Q2',value='95',document_id=d['id'])])
    old,new=s.observations();c=s.save_comparison(compare(old,new));monkeypatch.setattr(runtime,'repository',lambda:s)
    assert c['id'] in runtime.query_market_data.entrypoint(result_id=c['id'])
    assert 'NOT_FOUND' in runtime.query_market_data.entrypoint(result_id='missing-id')
    assert '92.50' not in runtime.query_market_data.entrypoint(result_id='missing-id')


def test_failed_provider_usage_is_unknown_and_terminal(monkeypatch):
    def fail(*a,**k):raise TimeoutError('SENSITIVE PROVIDER BODY')
    monkeypatch.setattr(OpenAIChat,'invoke',fail)
    m=BoundedOpenAIChat(id='test',api_key='offline-test',max_tokens=20);m.budget=Budget()
    with pytest.raises(TimeoutError):m.invoke(messages=[])
    r=m.budget.record()
    assert r['input_tokens'] is None and r['output_tokens'] is None
    assert r['calls'][0]['status']=='failed' and r['calls'][0]['finished']
    assert 'SENSITIVE' not in json.dumps(r)


def test_persist_failure_is_visible_after_rollback(tmp_path):
    s=Repository(tmp_path/'fail.db');a=s.attempt('d','v','r')
    with pytest.raises(RuntimeError):s.persist(a,[fact()],fail_after_first=True)
    failed=s.get('attempts',a['id'])
    assert failed['status']=='failed' and failed['finished_at'] and failed['error_type']=='RuntimeError'
    assert s.observations()==[]


def test_fetch_slow_chunks_obey_absolute_deadline(monkeypatch):
    import httpx
    from london_data import documents as d
    monkeypatch.setattr(d.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    class Slow(httpx.SyncByteStream):
        def __iter__(self):
            yield b'a'
            clock[0]=1001
            yield b'b'
    clock=[1];monkeypatch.setattr(d.time,'monotonic',lambda:clock[0])
    transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=Slow(),headers={'content-type':'text/html'}))
    with pytest.raises((ValueError,TimeoutError),match='DEADLINE'):d.fetch('https://example.org/report',{'example.org'},transport=transport,deadline=480)


def test_blocked_io_returns_by_deadline_and_discards_late_value():
    from london_data.deadlines import call_until
    started=time.monotonic()
    with pytest.raises(TimeoutError):call_until(lambda:time.sleep(.3),started+.03)
    assert time.monotonic()-started<.2


def test_native_steps_fail_closed_without_implicit_retries():
    from london_data.pipeline import make_workflow
    w=make_workflow()
    assert all(s.max_retries==0 and str(s.on_error)=='fail' for s in w.steps)
    with pytest.raises(KeyError):w.run({'document_key':'unregistered-negative-test'})


def test_query_agent_forces_readonly_data_tool_instead_of_spending_limit_on_skill():
    from london_data.runtime import create_agent_os
    agent=create_agent_os().agents[0]
    assert agent.tool_choice=={'type':'function','function':{'name':'query_market_data'}}


def test_failed_attempt_cannot_be_relabelled_as_success_on_retry(tmp_path):
    s=Repository(tmp_path/'immutable-failure.db');a=s.attempt('d','v','r')
    with pytest.raises(RuntimeError):s.persist(a,[fact()],fail_after_first=True)
    with pytest.raises(ValueError,match='NEW_ATTEMPT'):s.persist(a,[fact()])
    retry=s.attempt('d','v','r2');s.persist(retry,[fact()])
    assert s.get('attempts',a['id'])['status']=='failed' and s.get('attempts',retry['id'])['status']=='succeeded'


@pytest.mark.parametrize('metrics',[[],['rent','rent','vacancy']])
def test_empty_or_duplicate_extraction_never_becomes_successful_import(tmp_path,monkeypatch,metrics):
    from london_data import pipeline as p
    from agno.workflow.types import StepInput
    s=Repository(tmp_path/'partial.db');monkeypatch.setattr(p,'repository',lambda:s);monkeypatch.setattr(p,'config_version',lambda *a:'synthetic-v')
    output={'observations':[{'metric':m} for m in metrics]}
    monkeypatch.setattr(p,'extract',lambda *a:(output,{'run_id':'synthetic-no-model','budget':{'requests':0},'raw_output':output}))
    with pytest.raises(ValueError,match='MISSING_OR_DUPLICATE'):
        p.extract_step(StepInput(input={'document':{'id':'d'},'profile':{},'execution_id':'synthetic-empty-output','document_started_epoch':time.time()}))
    assert s.all('attempts')[0]['status']=='failed' and not s.observations()


def test_stream_budget_checked_before_each_yield(monkeypatch):
    from agno.models.response import ModelResponse
    def slow(*a,**k):
        yield ModelResponse(content='first')
        m.budget.started=time.monotonic()-481
        yield ModelResponse(content='late')
    monkeypatch.setattr(OpenAIChat,'invoke_stream',slow)
    m=BoundedOpenAIChat(id='test',api_key='offline-test',max_tokens=20);m.budget=Budget()
    stream=m.invoke_stream(messages=[]);assert next(stream).content=='first'
    with pytest.raises(ValueError):next(stream)
    assert m.budget.record()['calls'][0]['status']=='failed'
