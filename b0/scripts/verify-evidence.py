"""Check evidence semantics; PASS is derived from observed native run records."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'b0/evidence/api-results'
def read(name):
    return json.loads((out/f'{name}.json').read_text(encoding='utf-8-sig'))
checks={}
intro=read('T01-introduction')['body']
arithmetic=read('T01-arithmetic')['body']
checks['agent_two_real_runs']=all(r.get('status')=='COMPLETED' and r.get('run_id') and r.get('model_provider_data',{}).get('id') for r in (intro,arithmetic)) and '42' in arithmetic['content']
tools=read('T02-tools')['body']
checks['tool_invocation_in_run']=any(t.get('tool_name')=='add_numbers' and t.get('tool_args')=={'a':17,'b':25} and str(t.get('result'))=='42' for t in tools.get('tools',[]))
checks['tool_final_answer']=tools.get('status')=='COMPLETED' and '42' in str(tools.get('content',''))
actual=[json.loads(x) for x in (root/'b0/evidence/logs/tool-invocations.jsonl').read_text(encoding='utf-8').splitlines()]
native_tool=next((t for t in tools.get('tools',[]) if t.get('tool_name')=='add_numbers'),{})
checks['python_tool_executed']=any(t['a']==17 and t['b']==25 and t['result']==42 and abs(t['time']-native_tool.get('created_at',0))<2 for t in actual)
checks['session_context']='violet-cabin-629' in read('T03-recall')['body']['content']
w=read('T04-workflow')['body']
checks['workflow_two_steps']=w['status']=='COMPLETED' and [s['step_name'] for s in w['step_results']]==['Draft','Review'] and all(s['success'] for s in w['step_results'])
draft=w['step_results'][0]['content']
checks['workflow_output_enters_next_step']=any(m.get('role')=='user' and draft in str(m.get('content')) for m in w['step_executor_runs'][1]['messages'])
t=read('T05-team')['body']
members=t.get('member_responses',[])
checks['team_two_real_members']=t['status']=='COMPLETED' and {m.get('agent_id') for m in members}=={'b0-explainer','b0-reviewer'} and all(m.get('run_id') and m.get('status')=='COMPLETED' for m in members)
s=read('T06-skills')['body']
checks['native_skill_loaded']=any(t.get('tool_name')=='get_skill_instructions' and t.get('tool_args',{}).get('skill_name')=='code-review' and 'Code Review Skill' in str(t.get('result')) for t in s.get('tools',[]))
sched=read('T07-scheduler')
checks['natural_schedule_real_run']=sched['result']=='PASS' and sched['natural_run']['status']=='success' and bool(sched['natural_run']['run_id'])
checks['natural_schedule_disabled']=sched['final_disabled']['body']['enabled'] is False
failure=read('T07-scheduler-failure')
checks['scheduler_manual_trigger_failure']=failure.get('result')=='PASS' and failure.get('trigger',{}).get('status')==200 and failure.get('history',{}).get('data',[{}])[0].get('status')=='failed'
checks['failure_schedule_disabled']=failure.get('final_disabled',{}).get('body',{}).get('enabled') is False
checks.update(read('T08-restart-checks'))
result={'checks':checks,'all_pass':all(checks.values()),'scope':'Backend evidence only; browser evidence separately required.'}
(out/'verified-backend-checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['all_pass'] else 1)
