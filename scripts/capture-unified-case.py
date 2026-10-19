"""Copy actual completed native/provider/Skill evidence; never submits a request."""
import argparse
import hashlib
import json
import pathlib
import sqlite3
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'docs/delivery/unified-release-20261019-r1'
parser=argparse.ArgumentParser();parser.add_argument('label');parser.add_argument('session');args=parser.parse_args()
def decode(v):
    for _ in range(3):
        if not isinstance(v,str):break
        try:v=json.loads(v)
        except ValueError:break
    return v
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with sqlite3.connect((ROOT/'app/data/product/market.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    jobs=[json.loads(r[0]) for r in db.execute('select payload from jobs order by rowid desc')]
    job=next(j for j in jobs if j.get('kind')=='ask' and j.get('session_id')==args.session)
    assert job['status'] not in ['running','queued']
    report_id=job.get('result',{}).get('report_id')
    report=json.loads(db.execute('select payload from reports where id=?',(report_id,)).fetchone()[0]) if report_id else None
with sqlite3.connect((ROOT/'app/data/product/agno.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    sessions=[decode(r[0]) for r in db.execute('select runs from agno_sessions')]
    wanted=set(job.get('workflow_run_ids',[])+[job.get('run_id')])
    runs=[r for values in sessions for r in values if r.get('run_id') in wanted]
model_path=ROOT/'app/data/product/model-ledgers'/(hashlib.sha256(str(job.get('run_id')).encode()).hexdigest()+'.json')
ledger=decode(model_path.read_text(encoding='utf-8')) if model_path.exists() else None
audit_id=(job.get('skill_execution') or {}).get('audit_id')
skill_path=ROOT/'app/data/product/skill-ledgers'/((audit_id or 'none')+'.json')
skill=decode(skill_path.read_text(encoding='utf-8')) if skill_path.exists() else None
with urllib.request.urlopen('http://127.0.0.1:7788/api/market/release') as response:identity=json.load(response)
evidence=dict(label=args.label,identity=identity,job=job,report=report,native_runs=runs,model_ledger=ledger,skill_audit=skill)
text=json.dumps(evidence,ensure_ascii=False)
for secret in ['model.deepseek-acceptance-20261019.json','model.json','relay.json']:
    p=ROOT/'secrets'/secret
    if p.exists():
        key=json.loads(p.read_text(encoding='utf-8-sig')).get('api_key')
        assert not key or key not in text,'Refusing to persist secret bytes'
save(args.label+'.json',evidence)
print(json.dumps(dict(label=args.label,job_id=job['id'],run_id=job.get('run_id'),report_id=report_id,status=job['status'],
    workflow_run_ids=job.get('workflow_run_ids'),requests=(ledger or {}).get('requests'),
    input_tokens=(ledger or {}).get('input_tokens'),output_tokens=(ledger or {}).get('output_tokens'),
    selected_skills=(skill or {}).get('requested_skills'),geographies=((report or {}).get('artifact') or {}).get('scope',{}).get('geographies')),ensure_ascii=False))
