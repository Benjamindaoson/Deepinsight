import json
import pytest
from london_product.store import Store
from london_product.service import MarketService


@pytest.fixture
def svc(tmp_path):
    service = MarketService(Store(tmp_path))
    yield service
    service.pool.shutdown(wait=True)


def observation(svc, identity, *, geography='City', period='2026Q2', value='8', approved=True, definition='vacant stock share', metric='vacancy', unit='percent'):
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


def test_intent_and_parent_scope():
    from london_product.chat_report import resolve_scope
    q='Prepare a London office market report for Q2 2026. Compare City, West End and Canary Wharf, covering rents, vacancy, leasing activity and development pipeline.'
    scope=resolve_scope(q)
    assert scope['report_type']=='market_report'
    assert scope['observation_period']=='2026Q2'
    assert scope['geographies']==['City','West End','Canary Wharf']
    assert scope['metrics']==['rent','vacancy','takeup','supply']
    follow=resolve_scope('What about availability?',scope)
    assert follow['geographies']==scope['geographies']
    assert follow['observation_period']=='2026Q2'
    assert follow['metrics']==['availability']
    assert follow['report_type']=='topic_analysis'
    changed=resolve_scope('Analyse Canary Wharf in Q1 2026',scope)
    assert changed['geographies']==['Canary Wharf'] and changed['observation_period']=='2026Q1'
    assert resolve_scope('What is the latest published prime rent for the City?')['report_type']=='fact_answer'
    assert resolve_scope('What about Q1?',scope)['observation_period']=='2026Q1'


def test_institutional_html_is_structured_and_escapes_untrusted_evidence(svc):
    from london_product.chat_report import build_report, render_html
    observation(svc,'pending',approved=False)
    report=build_report(svc,'Prepare City Q2 2026 office market report')
    report['evidence'][0]['quote']='<script>alert(1)</script>'
    report['evidence'][0]['url']='javascript:alert(1)'
    output=render_html(report)
    assert '<table' in output and '<article' in output
    assert 'Source-reported observations' in output
    assert 'Pending review' in output
    assert '<script>' not in output and 'href="javascript:' not in output
    assert '&lt;script&gt;' in output
    assert report['generation_status']=='insufficient_evidence'


def test_combined_geography_is_related_context_never_standalone_coverage(svc):
    from london_product.chat_report import build_report
    observation(svc,'combined',geography='Canary Wharf & Docklands',approved=False)
    report=build_report(svc,'Analyse Canary Wharf vacancy Q2 2026')
    assert not report['market_snapshot']
    assert report['related_observations'][0]['geography']=='Canary Wharf & Docklands'
    assert report['related_observations'][0]['review_status']=='pending_review'
    assert report['evidence'][0]['id']=='combined'
    assert report['data_gaps'][0]['geography']=='Canary Wharf'
    assert all(c['status']=='unavailable' for c in report['charts'])
    latest=build_report(svc,'Latest Canary Wharf vacancy')
    assert latest['observation_period']=='2026Q2'
    assert latest['related_observations'][0]['fact_id']=='combined'
    assert not latest['market_snapshot']


def test_persist_and_explicit_gaps(svc):
    from london_product.chat_report import build_report, read_report
    observation(svc,'v')
    report=build_report(svc,'Prepare Q2 2026 market report comparing City and West End rents and vacancy')
    assert report['generation_status']=='partial'
    assert len(report['data_gaps'])==3
    assert report['market_snapshot'][0]['fact_id']=='v'
    assert report['evidence'][0]['document_sha256']
    assert read_report(svc.store,report['report_id'])['report_id']==report['report_id']
    assert report['generated_at']!='2026Q2'
    assert svc.store.get('reports',report['report_id'])['artifact']==report
    json.dumps(report)


def test_pending_and_tampered_original_never_charted(svc):
    from london_product.chat_report import build_report, read_report
    observation(svc,'pending',approved=False)
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    assert report['generation_status']=='insufficient_evidence'
    assert not report['key_findings']
    assert all(c['status']=='unavailable' for c in report['charts'])
    observation(svc,'approved',period='2026Q1',value='9')
    svc.store.update('facts','pending',dict(status='validated',human_review_status='approved'))
    ready=build_report(svc,'Analyse City vacancy Q2 2026 with a historical trend')
    line=next(c for c in ready['charts'] if c['type']=='time_series')
    assert line['status']=='ready'
    assert ready['calculations'][0]['absolute_change']=='-1'
    doc=svc.store.get('documents',svc.store.get('facts','pending')['document_id'])
    from pathlib import Path
    Path(doc['path']).write_bytes(b'tampered')
    stale=read_report(svc.store,ready['report_id'])
    assert stale['generation_status']=='insufficient_evidence'
    assert all(c['status']=='unavailable' for c in stale['charts'])
    assert 'EVIDENCE_CHANGED' in stale['publication_review']['codes']


@pytest.mark.parametrize('method', [None, 'unknown'])
def test_missing_method_cannot_support_approved_report_or_chart(svc, method):
    from london_product.chat_report import build_report
    for identity, period, value in [('old', '2026Q1', '6.8'), ('new', '2026Q2', '6.7')]:
        observation(svc, identity, geography='West End', period=period, value=value)
        svc.store.update('facts', identity, dict(method=method))
    report = build_report(svc, 'Analyse West End vacancy Q2 2026 with historical trend')
    assert report['generation_status'] == 'insufficient_evidence'
    assert all(c['status'] == 'unavailable' for c in report['charts'])
    assert not report['key_findings']


def test_regional_chart_requires_matching_definitions(svc):
    from london_product.chat_report import build_report
    observation(svc,'city')
    observation(svc,'west',geography='West End',definition='available space share')
    report=build_report(svc,'Compare City and West End vacancy in Q2 2026')
    chart=next(c for c in report['charts'] if c['type']=='regional_comparison')
    assert chart['status']=='unavailable'
    svc.store.update('facts','west',dict(definition='vacant stock share'))
    report=build_report(svc,'Compare City and West End vacancy in Q2 2026')
    chart=next(c for c in report['charts'] if c['type']=='regional_comparison')
    assert chart['status']=='ready' and len(chart['points'])==2


def test_unknown_annual_rent_and_wrong_period_are_gaps(svc):
    from london_product.chat_report import build_report
    observation(svc,'rent',metric='rent',unit='GBP/sqft',value='95')
    report=build_report(svc,'Latest City prime rent')
    assert report['generation_status']=='insufficient_evidence'
    assert not report['key_findings']
    observation(svc,'v',period='2026Q1')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    assert not report['market_snapshot']
    assert report['data_gaps']


def test_report_sse_and_json_round_trip(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    with TestClient(create_app(tmp_path,seed=False,scheduler=False)) as client:
        response=client.post('/api/market/ask',json=dict(message='Prepare City Q2 2026 office market report',mode='saved'))
        assert response.status_code==200
        events=[json.loads(x[6:]) for x in response.text.splitlines() if x.startswith('data: ')]
        assert any(e['type']=='progress' for e in events)
        artifact=next(e['report'] for e in events if e['type']=='report')
        assert events[-1]['type']=='done' and events[-1]['report_id']==artifact['report_id']
        assert client.get('/api/market/reports/'+artifact['report_id']+'?format=json').json()['report_id']==artifact['report_id']
        assert client.get('/api/market/reports').json()['items'][0]['generation_status']=='insufficient_evidence'


def test_ai_schema_cannot_change_numbers_or_promote_unsupported_claims(svc):
    from london_product.chat_report import build_report, attach_analysis
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    original=report['market_snapshot']
    content=dict(key_findings=[dict(text='Vacancy doubled to 99%.',classification='inference',evidence_ids=['v'])],
        risks=[dict(text='Demand caused vacancy to fall.',classification='inference',evidence_ids=['v'])],
        opportunities=[dict(text='There may be a need to investigate occupier requirements.',classification='scenario',evidence_ids=['invented'])],outlook=[])
    result=attach_analysis(svc.store,report['report_id'],content,run_id='mocked-provider-run')
    assert result['market_snapshot']==original
    assert not result['risks'] and not result['opportunities']
    assert result['ai_analysis']['status']=='withheld'
    assert result['publication_review']['semantic_approval'] is False
    assert result['generation_status']=='partial'
    result=attach_analysis(svc.store,report['report_id'],dict(opportunities=[dict(text='City rents will triple next year.',classification='scenario',evidence_ids=['v'])]))
    assert not result['opportunities']
    assert not result['ai_analysis']['draft']


def test_requested_missing_history_is_partial_and_stale_taxonomy_withheld(svc):
    from london_product.chat_report import build_report, read_report, attach_analysis
    observation(svc,'v')
    report=build_report(svc,'Analyse City vacancy Q2 2026 historical trend')
    assert report['generation_status']=='partial'
    assert any(g.get('component')=='history' for g in report['data_gaps'])
    svc.store.update('facts','v',dict(method='different survey'))
    stale=read_report(svc.store,report['report_id'])
    assert stale['generation_status']=='insufficient_evidence' and not stale['key_findings']
    changed=attach_analysis(svc.store,report['report_id'],dict(opportunities=[dict(text='Further study could investigate demand.',classification='scenario',evidence_ids=['v'])]))
    assert not changed['opportunities'] and not changed['ai_analysis']['draft']


def test_supply_partition_and_event_dates_are_explicit(svc):
    from london_product.chat_report import build_report
    a=observation(svc,'new',metric='supply',unit='sqft',value='100',definition='exclusive pipeline categories')
    b=observation(svc,'refurb',metric='supply',unit='sqft',value='200',definition='exclusive pipeline categories')
    for fid,category in [('new','new construction'),('refurb','refurbishment')]:
        svc.store.update('facts',fid,dict(partition_id='official-pipeline',mutually_exclusive=True,supply_category=category))
    for fid,date in [('event-a','2026-05-02'),('event-duplicate','2026-05-02'),('event-pub-only',None)]:
        svc.store.put('events',fid,dict(id=fid,title='Disclosed project',source_id='official',document_id=a['document_id'],
            geography='City',event_date=date,published_at='2026-05-03',status='pending_review',evidence=a['evidence']))
    report=build_report(svc,'Analyse City development pipeline Q2 2026')
    supply=next(c for c in report['charts'] if c['type']=='supply_structure')
    assert supply['status']=='ready' and len(supply['points'])==2
    timeline=next(c for c in report['charts'] if c['type']=='event_timeline')
    assert len(timeline['points'])==1 and timeline['points'][0]['date']=='2026-05-02'
    svc.store.update('facts',b['id'],dict(mutually_exclusive=False))
    report=build_report(svc,'Analyse City development pipeline Q2 2026')
    assert next(c for c in report['charts'] if c['type']=='supply_structure')['status']=='unavailable'


def test_rejected_and_source_restricted_evidence_downgrade(svc):
    from london_product.chat_report import build_report, read_report
    observation(svc,'v')
    report=build_report(svc,'City vacancy Q2 2026')
    svc.store.update('sources','official',dict(allow_llm=False))
    assert read_report(svc.store,report['report_id'])['generation_status']=='insufficient_evidence'
    assert not build_report(svc,'City vacancy Q2 2026')['market_snapshot']


def test_regional_area_conversion_preserves_raw_records(svc):
    from london_product.chat_report import build_report
    from decimal import Decimal
    observation(svc,'city',metric='availability',unit='sqft',value='1000',definition='available area')
    observation(svc,'west',geography='West End',metric='availability',unit='sqm',value='100',definition='available area')
    report=build_report(svc,'Compare City and West End availability Q2 2026')
    regional=next(c for c in report['charts'] if c['type']=='regional_comparison')
    assert regional['status']=='ready' and regional['unit']=='sqft'
    converted=next(p for p in regional['points'] if p['geography']=='West End')
    assert Decimal(converted['value'])==Decimal('1076.3910416709700')
    raw=next(f for f in report['market_snapshot'] if f['geography']=='West End')
    assert raw['value']=='100' and raw['unit']=='sqm'
    assert svc.store.get('facts','west')['unit']=='sqm'


@pytest.mark.parametrize('question',['Analyse City vacancy Q2 2026','City vacancy Q2 2026'])
def test_report_mode_never_releases_model_json_as_sse_tokens(tmp_path,question):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False)
    observation(app.state.market,'v')
    raw=json.dumps(dict(outlook=[dict(text='Premium occupier demand is extraordinarily strong.',classification='inference',evidence_ids=['v'])]))
    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))
        async def arun(self,*args,**kwargs):
            yield SimpleNamespace(event='ToolCallCompleted',run_id='offline',tool=SimpleNamespace(
                tool_name='search_market_evidence',tool_call_error=False,result=json.dumps(dict(facts=[dict(id='v')],events=[],documents={}))))
            yield SimpleNamespace(event='RunContent',run_id='offline',content=raw)
            yield SimpleNamespace(event='RunCompleted',run_id='offline')
    app.state.market.agent_factory=OfflineAgent
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json=dict(message=question,mode='agent'))
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    tokens=''.join(e['content'] for e in events if e['type']=='token')
    assert 'extraordinarily strong' not in tokens
    assert 'Structured report delivered' in tokens
    assert events[-1]['type']=='done'


def test_native_retrieval_persists_report_and_scope_without_model(svc):
    from agno.run import RunContext
    from london_product.intelligence import query_agent
    from agno.db.sqlite import SqliteDb
    observation(svc,'v')
    agent=query_agent(svc,SqliteDb(db_file=str(svc.store.root/'native.sqlite3')))
    tool=next(t for t in agent.tools if getattr(t,'name',None)=='search_market_evidence')
    state={}
    first=json.loads(tool.entrypoint(run_context=RunContext(run_id='one',session_id='session',session_state=state),query='Prepare City vacancy market report Q2 2026'))
    assert first['report_id'] and first['report_summary']['scope']['observation_period']=='2026Q2'
    second=json.loads(tool.entrypoint(run_context=RunContext(run_id='two',session_id='session',session_state=state),query='What about availability?'))
    assert second['report_summary']['scope']['geographies']==['City']
    assert second['report_summary']['scope']['observation_period']=='2026Q2'
    from agno.models.message import Message
    third=json.loads(tool.entrypoint(run_context=RunContext(run_id='three',session_id='session',session_state=state,
        messages=[Message(role='user',content='City vacancy Q1 2026')]),query='West End rent Q4 2025'))
    assert third['report_summary']['scope']['geographies']==['City']
    assert third['report_summary']['scope']['metrics']==['vacancy']
    assert third['report_summary']['scope']['observation_period']=='2026Q1'
    from types import SimpleNamespace
    agent.post_hooks[0](SimpleNamespace(run_id='one',content=json.dumps(dict(opportunities=[dict(text='City rents will triple next year.',classification='scenario',evidence_ids=['v'])])),tools=[dict(tool_name='search_market_evidence',result=json.dumps(first))]))
    assert svc.store.get('reports',first['report_id'])['artifact']['ai_analysis']['status']=='withheld'
    from london_product.safe_answer import project_run
    projected=project_run(dict(agent_id='london-market-agent',status='COMPLETED',content='City rents will triple next year.',run_id='one',tools=[dict(tool_name='search_market_evidence',result=json.dumps(first))]),svc.store)
    assert 'triple' not in projected['answer']
    assert projected['report_id']==first['report_id']
