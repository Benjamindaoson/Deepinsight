"""Freeze current code/config/test identities; never read credentials or build caches."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/delivery/final-delivery-20261019'
manifest={}
for folder in ['app/london_product','app/london_data','app/tests','app/product_skills','app/migrations','app/scripts','app/frontend/src','app/frontend/tests','app/docs/product']:
 for p in (ROOT/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:manifest[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['app/pytest.ini','app/requirements-product.lock.txt','app/requirements.lock.txt','app/frontend/package.json','app/frontend/pnpm-lock.yaml','app/frontend/tsconfig.json','app/frontend/next.config.ts','app/frontend/eslint.config.mjs']:
 p=ROOT/name
 if p.is_file():manifest[name]=hashlib.sha256(p.read_bytes()).hexdigest()
target=OUT/(sys.argv[1]+'.json')
target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(dict(path=str(target),files=len(manifest))))
if len(sys.argv)>2:
 before=json.loads((OUT/(sys.argv[2]+'.json')).read_text(encoding='utf-8'))
 changed=[k for k in sorted(set(before)|set(manifest)) if before.get(k)!=manifest.get(k)]
 (OUT/(sys.argv[1]+'-drift.json')).write_text(json.dumps(changed,indent=2),encoding='utf-8')
 print(json.dumps(dict(drift=changed)))
 raise SystemExit(bool(changed))
