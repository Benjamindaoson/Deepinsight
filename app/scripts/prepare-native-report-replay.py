"""Offline browser fixture: real saved report, simulated native session, zero model calls."""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from agno.db.sqlite import SqliteDb
from agno.session.agent import AgentSession
from agno.run.agent import RunOutput, RunInput
from agno.run import RunStatus
from agno.models.response import ToolExecution
from london_product.store import Store

directory=ROOT/'docs/delivery/chat-report-acceptance/runtime'
store=Store(directory)
report=next(r['artifact'] for r in store.all('reports') if r.get('report_type')=='market_report')
sid='offline-chat-report-replay'
pack=dict(facts=[],events=[],documents={},report_id=report['report_id'],report_summary=dict(scope=report['scope']))
run=RunOutput(run_id='offline-replay-run',agent_id='london-market-agent',session_id=sid,
    input=RunInput(input_content='[OFFLINE UI FIXTURE — no model execution] '+report['query']),
    content='[OFFLINE UI FIXTURE — no model execution] Restore the existing saved report.',
    status=RunStatus.completed,created_at=int(time.time()),
    tools=[ToolExecution(tool_name='search_market_evidence',tool_call_id='offline-tool',result=json.dumps(pack))])
db=SqliteDb(id='london-product',db_file=str(directory/'agno.sqlite3'))
db.upsert_session(AgentSession(session_id=sid,agent_id='london-market-agent',runs=[run],
    session_data=dict(session_name='OFFLINE report replay · no model call'),metadata=dict(offline_acceptance_fixture=True),
    created_at=int(time.time()),updated_at=int(time.time())))
print(json.dumps(dict(session_id=sid,report_id=report['report_id'],model_calls=0,simulated_native_session=True)))
