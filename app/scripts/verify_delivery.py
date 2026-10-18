"""Read-only protected-identity/security checks; writes B1 receipts only."""
import json,hashlib,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.extraction import ROOT

baseline=json.loads((ROOT/'b1/evidence/g0/protected-baseline.json').read_text(encoding='utf8'))
out={'checked_at':datetime.now(timezone.utc).isoformat(),'protected_files':{},'upstream':{},'secret_matches':[],'database_files_scanned':[]}
for k,v in baseline.items():
    if isinstance(v,str):
        p=ROOT/k;out['protected_files'][k]=p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==v
    elif isinstance(v,dict) and 'head' in v:
        p=ROOT/'upstream'/k
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip()
        diff=subprocess.check_output(['git','diff','HEAD','--'],cwd=p,text=True)
        out['upstream'][k]={'head':head,'head_matches':head==v['head'],'tracked_diff_matches':diff==v['diff']}
credentials=json.loads((ROOT/'secrets/model.json').read_text(encoding='utf-8-sig'))
needles=[str(v).encode() for k,v in credentials.items() if k in ['api_key'] and v]
checked=0
for base in [ROOT/'b1',ROOT/'app']:
    for p in base.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ['.venv','node_modules','__pycache__','.codegraph']):continue
        is_db=p.suffix.lower() in ['.db','.sqlite'] or p.name.endswith(('-wal','-shm'))
        if p.suffix.lower() not in ['.json','.md','.log','.txt','.html','.py','.ps1','.sh','.yaml','.xml'] and not is_db:continue
        if is_db:out['database_files_scanned'].append(str(p.relative_to(ROOT)))
        body=p.read_bytes();checked+=1
        if any(n in body for n in needles):out['secret_matches'].append(str(p.relative_to(ROOT)))
out['text_files_scanned']=checked
out['pass']=all(out['protected_files'].values()) and all(x['head_matches'] and x['tracked_diff_matches'] for x in out['upstream'].values()) and not out['secret_matches']
(ROOT/'b1/evidence/g0/final-boundary-check.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps({'pass':out['pass'],'protected_count':len(out['protected_files']),'upstream_count':len(out['upstream']),'text_files_scanned':checked,'mismatch_paths':[k for k,v in out['protected_files'].items() if not v],'secret_match_paths':out['secret_matches']},indent=2))
if not out['pass']:raise SystemExit(1)
