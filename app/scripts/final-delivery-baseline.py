"""Read-only live inventory, online backups and isolated final acceptance copy."""
import hashlib, json, sqlite3, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/delivery/final-delivery-20261019'
OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={}
for folder in ['app/london_product','app/london_data','app/frontend/src','app/tests','app/product_skills','app/scripts','app/migrations']:
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:manifest[p.relative_to(ROOT).as_posix()]=sha(p)
receipt=dict(at=datetime.now(timezone.utc).isoformat(),cwd=str(ROOT),source_sha256=manifest,
    git={k:subprocess.run(['git',*a],cwd=ROOT,capture_output=True,text=True,encoding='utf-8').stdout for k,a in {'head':['rev-parse','HEAD'],'status':['status','--short']}.items()},databases={})
for label,directory in [('live',ROOT/'app/data/product'),('real-source',ROOT/'docs/delivery/real-e2e-20261019/runtime')]:
    stats={}
    for name in ['market.sqlite3','agno.sqlite3']:
        source=directory/name
        if not source.exists():continue
        dest=OUT/'baseline'/label/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise SystemExit('Baseline exists; preserve it')
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(dest) as dst:
            src.backup(dst)
            stats[name]=dict(path=str(source),backup=str(dest),sha256=sha(dest),counts={t:src.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for (t,) in src.execute("SELECT name FROM sqlite_master WHERE type='table'")})
    receipt['databases'][label]=stats
target=OUT/'isolated';target.mkdir(exist_ok=True)
with sqlite3.connect(OUT/'baseline/real-source/market.sqlite3') as src,sqlite3.connect(target/'market.sqlite3') as dst:src.backup(dst)
with sqlite3.connect(target/'market.sqlite3') as db:
    facts=[json.loads(x[0]) for x in db.execute('SELECT payload FROM facts')]
    docs=[json.loads(x[0]) for x in db.execute('SELECT payload FROM documents')]
receipt['data_summary']=dict(facts=len(facts),metrics=dict(Counter(f.get('metric') for f in facts)),review=dict(Counter(str(f.get('human_review_status')) for f in facts)),geographies=dict(Counter(f.get('geography') for f in facts)))
provenance=[]
for d in docs:
    p=Path(d.get('path',''))
    provenance.append(dict(id=d['id'],url=d.get('url'),exists=p.is_file(),hash_matches=p.is_file() and sha(p)==d.get('sha256')))
(OUT/'baseline.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'original-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
print(json.dumps(dict(data=receipt['data_summary'],originals=len(docs),verified=sum(d['hash_matches'] for d in provenance)),ensure_ascii=False))
