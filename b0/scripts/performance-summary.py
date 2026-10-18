"""Summarize observed request latency and per-request model message metrics."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
p=root/'b0/evidence/api-results'
names=['T01-introduction','T01-arithmetic','T02-tools','T03-context','T03-recall','T04-workflow','T05-team','T06-skills']
out=[]
for name in names:
    receipt=json.loads((p/f'{name}.json').read_text(encoding='utf-8'))
    body=receipt['body']
    runs=body.get('step_executor_runs',[body])+body.get('member_responses',[])
    model_messages=[]
    for run in runs:
        # History messages belong to earlier runs and must not be counted again.
        model_messages.extend(m for m in run.get('messages',[]) if m.get('role')=='assistant'
            and m.get('metrics') and m.get('created_at',0)>=run.get('created_at',0))
    metrics={k:sum(m['metrics'].get(k,0) or 0 for m in model_messages)
             for k in ('input_tokens','output_tokens','total_tokens')}
    out.append({'test':name,'seconds':receipt['elapsed_seconds'],'run_id':body['run_id'],
                'observed_model_calls':len(model_messages), 'reported_tokens':metrics,
                'basis':'assistant messages carrying metrics in the current run; excludes earlier session history; includes workflow steps and team member runs'})
result={'measurements':out,'money_cost':'NOT AVAILABLE: relay billing not exposed',
        'scope':'One observed run per test, no concurrency/percentile benchmark; token counters are Agno/provider reported, not billing receipts.'}
scheduled=json.loads((p/'T07-scheduled-agent-run.json').read_text(encoding='utf-8'))['body']
schedule=json.loads((p/'T07-scheduler.json').read_text(encoding='utf-8'))['natural_run']
messages=[m for m in scheduled.get('messages',[]) if m.get('role')=='assistant' and m.get('metrics')]
result['scheduler']={'trigger_to_completion_seconds':schedule['completed_at']-schedule['triggered_at'],
    'run_id':scheduled['run_id'],'observed_model_calls':len(messages),
    'reported_tokens':scheduled.get('metrics'), 'basis':'one natural run, persisted Agent run metrics'}
(p/'performance-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
