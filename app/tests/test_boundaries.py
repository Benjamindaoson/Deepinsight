import pytest
from test_foundation import fact
from london_data.validation import validate
from london_data.extraction import Budget,BoundedOpenAIChat
from agno.models.openai import OpenAIChat
from agno.models.response import ModelResponse


def test_streaming_provider_requests_are_budgeted(monkeypatch):
    monkeypatch.setattr(OpenAIChat,'invoke_stream',lambda *a,**k:iter([ModelResponse(content='fixture')]))
    m=BoundedOpenAIChat(id='fixture',api_key='offline-test',max_tokens=10);m.budget=Budget(max_requests=1)
    list(m.invoke_stream(messages=[]))
    with pytest.raises(ValueError):list(m.invoke_stream(messages=[]))


def test_geography_and_metric_subject_must_be_in_evidence():
    f=fact(geography='City',evidence={'segment_id':'p1','quote':'West End prime rent £92.50 per sq ft per annum'})
    assert validate(f,[{'segment_id':'p1','text':f['evidence']['quote']}])['status']=='needs_review'


def test_negative_or_out_of_range_market_values_rejected():
    f=fact(metric='vacancy',value='120',unit='percent',currency=None,evidence={'segment_id':'p1','quote':'City vacancy 120%'})
    assert validate(f,[{'segment_id':'p1','text':f['evidence']['quote']}])['status']=='needs_review'


def test_extraction_identity_includes_profile_definitions():
    from london_data.extraction import config_version
    assert config_version({'unit':'unknown'})!=config_version({'unit':'annual-confirmed'})


def test_fetch_redirects_cannot_reach_private_target(monkeypatch):
    import httpx
    from london_data import documents as d
    monkeypatch.setattr(d.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(302,headers={'location':'https://127.0.0.1/secret'})
    with pytest.raises(ValueError):d.fetch('https://example.org/report',{'example.org'},transport=httpx.MockTransport(handler))
    assert len(calls)==1


def test_fetch_timeout_and_size_limit(monkeypatch):
    import httpx
    from london_data import documents as d
    monkeypatch.setattr(d.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    def timeout(req):raise httpx.ReadTimeout('test timeout')
    with pytest.raises(httpx.ReadTimeout):d.fetch('https://example.org/r',{'example.org'},transport=httpx.MockTransport(timeout))
    monkeypatch.setattr(d,'MAX_BYTES',5)
    with pytest.raises(ValueError):d.fetch('https://example.org/r',{'example.org'},transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'123456',headers={'content-type':'text/html'})))


def test_reprocessing_keeps_only_one_current_validated_fact(tmp_path):
    from london_data.store import Repository
    s=Repository(tmp_path/'reprocess.db');d=s.snapshot('bnp','https://example.org/a',b'v1','text/html',None,[])
    a=s.attempt(d['id'],'config1','run1');s.persist(a,[fact(document_id=d['id'])])
    b=s.attempt(d['id'],'config2','run2');s.persist(b,[fact(document_id=d['id'])])
    assert len(s.observations())==1
    assert len(s.observations(include_all=True))==2
    assert s.observations()[0].get('supersedes')


def test_readonly_query_escapes_untrusted_values(tmp_path,monkeypatch):
    from london_data.store import Repository
    from london_data import runtime
    s=Repository(tmp_path/'read.db');d=s.snapshot('bnp','https://example.org/a',b'x','text/html',None,[])
    a=s.attempt(d['id'],'c','run');s.persist(a,[fact(document_id=d['id'],geography='<script>bad()</script>',status='needs_review')])
    monkeypatch.setattr(runtime,'repository',lambda:s)
    result=runtime.query_market_data.entrypoint('all')
    assert '<script>' not in result and '&lt;script&gt;' in result


def test_unavailable_comparison_is_displayed_as_unavailable(tmp_path,monkeypatch):
    from london_data.store import Repository
    from london_data.comparison import compare
    from london_data import runtime
    s=Repository(tmp_path/'display.db')
    d=s.snapshot('bnp','https://example.org/a',b'x','text/html',None,[])
    a=s.attempt(d['id'],'v','r');s.persist(a,[fact(document_id=d['id'],unit='unknown',status='needs_review'),fact(document_id=d['id'],unit='unknown',status='needs_review',period='2026Q2')])
    old,new=s.observations(include_all=True)
    c=compare(old,new)
    s.save_comparison(c);monkeypatch.setattr(runtime,'repository',lambda:s)
    result=runtime.query_market_data.entrypoint('all')
    assert 'None%' not in result and 'N/A' in result


def test_malformed_candidate_rejected_without_unhandled_exception():
    assert validate('not-json',[])['status']=='rejected'


def test_disclosure_precision_must_match_quote():
    f=fact(precision='0.5')
    assert validate(f,[{'segment_id':'p3','text':f['evidence']['quote']}])['status']=='needs_review'


def test_model_cannot_relabel_publisher_or_period():
    f=fact(source_id='invented')
    profile={'source_id':'bnp','series':'office','metrics':{}}
    assert validate(f,[{'segment_id':'p3','text':f['evidence']['quote']}],profile=profile,expected_period='2026Q2')['status']=='needs_review'


@pytest.mark.parametrize('value,quote,expected',[('3200000','Central London take-up 3.20m sq ft','10000'),('92.5','City prime rent £92.50 per sq ft','0.01'),('95','City prime rent £95 per sq ft','1'),('8.4','Central London vacancy 8.4%','0.1')])
def test_source_disclosure_precision_is_deterministic(value,quote,expected):
    from london_data.contracts import source_precision
    assert source_precision(value,quote)==expected


def test_raw_model_cannot_supply_computed_precision():
    from london_data.contracts import RawObservation
    with pytest.raises(Exception):RawObservation.model_validate(fact())


def test_numeric_lexeme_parser_ignores_punctuation_commas():
    from london_data.contracts import source_precision
    assert source_precision('92.5','City prime rents increased 8.8%, to £92.50 per sq ft.')=='0.01'


def test_approximate_literal_is_preserved_without_changing_value():
    from london_data.contracts import source_precision
    assert source_precision('2750000','Take-up in Central London totalled c.2.75m sq ft')=='10000'


def test_overall_html_metric_can_use_explicit_report_title_context():
    f=fact(metric='vacancy',value='10.1',period='2024Q3',precision='0.1',unit='percent',currency=None,geography='Central London',definition='overall_office_vacancy',grade='all',evidence={'segment_id':'li1','quote':'Vacancy in Q3 2024 was 10.1%'})
    seg={'segment_id':'li1','text':f['evidence']['quote'],'scope_text':'Central London Office Market Update Q3 2024'}
    assert validate(f,[seg])['status']=='validated'
    f['evidence']['quote']='City vacancy in Q3 2024 was 10.1%';seg['text']=f['evidence']['quote']
    assert validate(f,[seg])['status']=='needs_review'


def test_reprocessed_pending_facts_keep_one_current_revision(tmp_path):
    from london_data.store import Repository
    s=Repository(tmp_path/'pending.db');d=s.snapshot('bnp','https://example.org/a',b'x','text/html',None,[])
    a=s.attempt(d['id'],'v1','r1');s.persist(a,[fact(document_id=d['id'],status='needs_review')])
    a=s.attempt(d['id'],'v2','r2');s.persist(a,[fact(document_id=d['id'],status='needs_review')])
    assert len([o for o in s.observations(include_all=True) if o['status']!='superseded'])==1


def test_late_provider_response_cannot_be_published():
    import time
    b=Budget();b.before(100,100);b.started=time.monotonic()-481
    with pytest.raises(ValueError):b.after(100,10)


def test_idle_chat_runtime_receives_fresh_per_run_budget():
    import time
    from types import SimpleNamespace
    m=BoundedOpenAIChat(id='fixture',api_key='offline-test',max_tokens=10);m.budget=Budget();m.reset_budget_per_run=True;m.budget.started=time.monotonic()-600
    m._reserve((),{'messages':[],'run_response':SimpleNamespace(run_id='new-user-run')})
    assert m.budget.requests==1
