"""Real AgentOS HTTP tests. Outputs are recorded, never synthesized."""
import argparse
import json
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'b0/evidence/api-results'

def save(name, value):
    (OUT / f'{name}.json').write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')

def run(entity, ident, message, name, session_id=None):
    data = {'message': message, 'stream': 'false', 'stream_events': 'true'}
    if session_id:
        data['session_id'] = session_id
    previous=OUT/f'{name}.json'
    if previous.exists():
        previous.rename(OUT/f'{name}.previous-{time.time_ns()}.json')
    start = time.monotonic()
    try:
        with httpx.Client(timeout=180, trust_env=False) as client:
            response = client.post(f'http://127.0.0.1:7777/{entity}/{ident}/runs', data=data)
    except Exception as error:
        save(name,{'http_status':None,'message':message,'body':{'status':'ERROR'},'error':str(error)})
        raise
    try:
        body = response.json()
    except ValueError:
        body = response.text
    result = {'http_status': response.status_code, 'elapsed_seconds': round(time.monotonic()-start,3),
              'message': message, 'body': body}
    save(name, result)
    print(name, response.status_code, result['elapsed_seconds'],
          json.dumps(body, ensure_ascii=False)[:450], flush=True)
    if response.status_code!=200 or not isinstance(body,dict) or body.get('status')!='COMPLETED' or not body.get('run_id'):
        raise RuntimeError(f'{name}: native run did not complete; see saved receipt')
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('test', choices=['agent','tools','sessions','workflow','team','skills'])
    args = p.parse_args()
    if args.test == 'agent':
        run('agents','b0-agent','Please introduce yourself in one sentence.','T01-introduction')
        run('agents','b0-agent','What is 17 plus 25? Give the numerical answer.','T01-arithmetic')
    elif args.test == 'tools':
        run('agents','b0-agent','Use the add_numbers tool to calculate 17 + 25.','T02-tools')
    elif args.test == 'sessions':
        for stale in ('T03-session-id','T03-recall'):
            old=OUT/f'{stale}.json'
            if old.exists():
                old.rename(OUT/f'{stale}.previous-{time.time_ns()}.json')
        first = run('agents','b0-agent','Remember this neutral test marker: violet-cabin-629. Reply briefly.','T03-context')
        sid = first['body'].get('session_id') if isinstance(first['body'],dict) else None
        if sid:
            save('T03-session-id', {'session_id':sid})
            run('agents','b0-agent','What neutral test marker did I ask you to remember?','T03-recall',sid)
    elif args.test == 'workflow':
        run('workflows','b0-workflow','Explain why reproducible tests matter. Include the marker FLOW-629 in the draft and improved answer.','T04-workflow')
    elif args.test == 'team':
        run('teams','b0-team','Explain the advantages of Python for data processing. Have both members contribute and summarize their views.','T05-team')
    elif args.test == 'skills':
        run('agents','b0-skills','Load the native code-review skill instructions, then review: def average(xs): return sum(xs)/len(xs). Mention one correctness risk.','T06-skills')
