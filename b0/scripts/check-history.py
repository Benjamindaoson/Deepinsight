import argparse
import json
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[2]
out=root/'b0/evidence/api-results'
p=argparse.ArgumentParser()
p.add_argument('phase',choices=['before','after'])
args=p.parse_args()
sid=json.loads((out/'T03-session-id.json').read_text())['session_id']
sched=json.loads((out/'T07-scheduler.json').read_text())['schedule_id']
team_sid=json.loads((out/'T05-team.json').read_text(encoding='utf-8'))['body']['session_id']
workflow_sid=json.loads((out/'T04-workflow.json').read_text(encoding='utf-8'))['body']['session_id']
routes={
  'sessions':'/sessions?db_id=b0-sqlite&type=agent',
  'context_runs':f'/sessions/{sid}/runs?db_id=b0-sqlite&type=agent',
  'team_runs':f'/sessions/{team_sid}/runs?db_id=b0-sqlite&type=team',
  'workflow_runs':f'/sessions/{workflow_sid}/runs?db_id=b0-sqlite&type=workflow',
  'schedules':'/schedules',
  'schedule_history':f'/schedules/{sched}/runs',
  'traces':'/traces?db_id=b0-sqlite',
}
receipt={}
with httpx.Client(base_url='http://127.0.0.1:7777',trust_env=False,timeout=20) as c:
    for label,route in routes.items():
        r=c.get(route)
        receipt[label]={'route':route,'status':r.status_code,'body':r.json()}
    if args.phase=='before':
        trace_rows=receipt['traces']['body'].get('data',[])
        if trace_rows:
            trace_id=trace_rows[0]['trace_id']
            r=c.get(f'/traces/{trace_id}',params={'db_id':'b0-sqlite'})
            receipt['persisted_trace']={'trace_id':trace_id,'status':r.status_code,'body':r.json()}
    else:
        initial=json.loads((out/'T08-history-before.json').read_text(encoding='utf-8'))
        if 'persisted_trace' in initial:
            trace_id=initial['persisted_trace']['trace_id']
            r=c.get(f'/traces/{trace_id}',params={'db_id':'b0-sqlite'})
            receipt['persisted_trace']={'trace_id':trace_id,'status':r.status_code,'body':r.json()}
(out/f'T08-history-{args.phase}.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print({k:v['status'] for k,v in receipt.items()})
if args.phase=='after':
    before=json.loads((out/'T08-history-before.json').read_text())
    checks={
      'session_runs_equal':bool(receipt['context_runs']['body']) and before['context_runs']['body']==receipt['context_runs']['body'],
      'expected_agent_run_present':json.loads((out/'T03-recall.json').read_text(encoding='utf-8'))['body']['run_id'] in {r['run_id'] for r in receipt['context_runs']['body']},
      'schedule_history_equal':bool(receipt['schedule_history']['body']['data']) and before['schedule_history']['body']['data']==receipt['schedule_history']['body']['data'],
      'expected_schedule_run_present':json.loads((out/'T07-scheduler.json').read_text(encoding='utf-8'))['natural_run']['id'] in {r['id'] for r in receipt['schedule_history']['body']['data']},
      'team_runs_equal':bool(receipt['team_runs']['body']) and before['team_runs']['body']==receipt['team_runs']['body'],
      'workflow_runs_equal':bool(receipt['workflow_runs']['body']) and before['workflow_runs']['body']==receipt['workflow_runs']['body'],
      'trace_persists':bool(receipt.get('persisted_trace')) and before.get('persisted_trace')==receipt.get('persisted_trace'),
      'all_schedules_disabled':all(not x['enabled'] for x in receipt['schedules']['body']['data']),
      'http_ok':all(v['status']==200 for v in receipt.values()),
    }
    (out/'T08-restart-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(checks)
    raise SystemExit(0 if all(checks.values()) else 1)
raise SystemExit(0 if all(v['status']==200 for v in receipt.values()) else 1)
