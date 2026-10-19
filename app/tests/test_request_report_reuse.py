"""Exercise the API plus the actual retrieval tool without external inference."""
import json
import pytest
from types import SimpleNamespace
from agno.db.sqlite import SqliteDb
from agno.models.message import Message
from agno.run import RunContext
from fastapi.testclient import TestClient
from london_product.intelligence import query_agent
from london_product.runtime import create_app
from test_chat_report import observation


def test_api_and_retrieval_share_one_report_per_request(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    observation(service,'v')
    native=query_agent(service,SqliteDb(db_file=str(tmp_path/'native.sqlite3')))
    loader=next(t for t in native.tools if getattr(t,'name',None)=='load_market_skills')
    tool=next(t for t in native.tools if getattr(t,'name',None)=='search_market_evidence')
    retrieved=[]

    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))

        async def arun(self,message,**kwargs):
            run_id='offline-'+str(len(retrieved))
            context=RunContext(run_id=run_id,session_id='session',session_state={},
                messages=[Message(role='user',content=message)])
            loaded=loader.entrypoint(run_context=context,skill_names=['market-intelligence'])
            yield SimpleNamespace(event='ToolCallCompleted',run_id=run_id,tool=SimpleNamespace(
                tool_name='load_market_skills',tool_call_error=False,result=loaded))
            result=tool.entrypoint(run_context=context,query='City vacancy Q2 2026')
            retrieved.append(json.loads(result))
            yield SimpleNamespace(event='ToolCallCompleted',run_id=run_id,tool=SimpleNamespace(
                tool_name='search_market_evidence',tool_call_error=False,result=result))
            yield SimpleNamespace(event='RunError',content='insufficient_user_quota',run_id=run_id)

    service.agent_factory=OfflineAgent
    with TestClient(app) as client:
        for question in ['Analyse City vacancy Q2 2026','Compare City and Canary Wharf vacancy Q2 2026']:
            response=client.post('/api/market/ask',json=dict(message=question,mode='agent'))
            events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            report_event=next(e for e in events if e['type']=='report')
            assert retrieved[-1]['report_id']==report_event['report_id']
            assert retrieved[-1]['report_summary']['scope']==report_event['report']['scope']
            assert events[-1]['code']=='PROVIDER_QUOTA_EXHAUSTED'
    assert len(service.store.all('reports'))==2
    assert retrieved[0]['report_id']!=retrieved[1]['report_id']


def test_native_post_hook_leaves_api_owned_analysis_to_orchestrator(tmp_path):
    from london_product.chat_report import ACTIVE_REPORT, build_report
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    observation(service,'v')
    artifact=build_report(service,'Analyse City vacancy Q2 2026',analysis_context=dict(submission_id='api'))
    native=query_agent(service,SqliteDb(db_file=str(tmp_path/'native.sqlite3')))
    token=ACTIVE_REPORT.set(artifact['report_id'])
    try:
        with pytest.raises(Exception, match='SKILL_EXECUTION_INCOMPLETE'):
            native.post_hooks[0](SimpleNamespace(run_id='offline',content=json.dumps(dict(outlook=[])),
                tools=[dict(tool_name='search_market_evidence',result=json.dumps(dict(report_id=artifact['report_id'])))]))
        assert service.store.get('reports',artifact['report_id'])['artifact']==artifact
    finally:
        ACTIVE_REPORT.reset(token)
        service.pool.shutdown(wait=True)
