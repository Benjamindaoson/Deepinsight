"""Verify saved browser network evidence and index observed UI screenshots."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
p=root/'b0/evidence'
def events(name):
    data=json.loads((p/'api-results'/name).read_text(encoding='utf-8'))
    return [json.loads(line[6:]) for line in data['body'].splitlines() if line.startswith('data: ')]
tool=events('ui-tool-stream-new-session.json')
team=events('ui-team-stream.json')
screenshots=['01-ui-connected.png','02-ui-agent-reply.png','03-ui-stream-in-progress.png',
 '05-ui-tool-new-session.png','06-session-before-refresh.png','07-session-after-refresh.png',
 '08-session-after-runtime-restart.png','09-ui-team-selector.png','10-ui-team-reply.png',
 '11-runtime-docs.png','12-scheduler-real-history.png','14-workflow-real-run.png']
checks={
 'tool_native_event':any(e['event']=='ToolCallCompleted' and e.get('tool',{}).get('tool_name')=='add_numbers'
   and e['tool'].get('tool_args')=={'a':17,'b':25} and e['tool'].get('result')=='42' for e in tool),
 'tool_final_answer':any(e['event']=='RunCompleted' and '42' in e.get('content','') for e in tool),
 'stream_content_events':sum(e['event']=='RunContent' for e in tool)>0,
 'team_two_members':{e.get('agent_id') for e in team if e['event']=='RunCompleted'}=={'b0-explainer','b0-reviewer'},
 'team_final':any(e['event']=='TeamRunCompleted' and e.get('content') for e in team),
 'screenshots_present':all((p/'screenshots'/name).is_file() for name in screenshots),
}
receipt={'checks':checks,'all_pass':all(checks.values()),'screenshots':screenshots,
 'browser':'Chrome via cua_repl',
 'observed_session_id':'489ed5fa-1f60-40dc-9907-14af720ed95e',
 'observed_session_marker':'violet-cabin-629',
 'manual_observations':['Agent and Team selectors visible','Two required Agent prompts sent through UI',
 'Same saved Session visible before refresh, after refresh, and after backend restart',
 'No Workflow mode in the original UI; backend run screenshot is not a UI feature claim'],
 'known_anomaly':{'evidence':'ui-tool-stream.json','description':'One multi-turn model reply off topic after correct tool execution; isolated new-session retry passed. Both records retained.'},
 'limits':'This validates saved network events and artifact presence; visual actions/restoration were observed live and indexed here, not inferred from file existence alone.'}
(p/'api-results/browser-acceptance.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
raise SystemExit(0 if receipt['all_pass'] else 1)
