"""Freeze read-only acceptance evidence. Never invokes a model or approves facts."""
import hashlib,json,sys
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import now
OUT=ROOT/'docs/delivery/real-e2e-20261019'
rid=json.loads((OUT/'FINAL_EVIDENCE_RECEIPT.json').read_text(encoding='utf-8'))['report_id']
base='http://localhost:7785'
checks=[]
for fmt,name in [('json','FINAL_EVIDENCE_REPORT.json'),('html','London-Office-Q2-2026.html'),('markdown','London-Office-Q2-2026.md')]:
 response=requests.get(f'{base}/api/market/reports/{rid}',params={'format':fmt},timeout=20)
 assert response.status_code==200
 (OUT/name).write_bytes(response.content)
 checks.append(dict(format=fmt,status=response.status_code,bytes=len(response.content),sha256=hashlib.sha256(response.content).hexdigest()))
r=json.loads((OUT/'FINAL_EVIDENCE_REPORT.json').read_text(encoding='utf-8'))
assert r['generation_status']=='partial' and r['ai_analysis'] is None
ready=[c for c in r['charts'] if c['status']=='ready']
assert len(ready)==1 and [p['value'] for p in ready[0]['points']]==['6.8','6.7']
identity=requests.get(base+'/api/market/runtime-identity',timeout=20).json();assert not identity['paid_allowed']
(OUT/'RUNTIME_IDENTITY.json').write_text(json.dumps(identity,indent=2,ensure_ascii=False),encoding='utf-8')
files=[]
for pattern in ['app/london_product/*.py','app/london_data/*.py','app/tests/test_*.py','app/frontend/src/lib/*.ts','app/frontend/src/components/market/*','app/frontend/tests/*.mjs','openspec/changes/model-output-and-real-data-acceptance/**/*.md']:
 for p in ROOT.glob(pattern):
  if p.is_file():files.append(p)
files += [ROOT/'app/frontend/.next-real-e2e-verified/BUILD_ID',ROOT/'app/frontend/package.json',ROOT/'app/frontend/next.config.ts']
source_dir=OUT/'source-freeze'
for p in files:
 dest=source_dir/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
manifest=dict(at=now(),report_id=rid,report_status='partial',model_status='BLOCKED_PROVIDER_QUOTA',http_checks=checks,
 source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},build_id=(ROOT/'app/frontend/.next-real-e2e-verified/BUILD_ID').read_text().strip(),
 live_receipt_sha256=hashlib.sha256((OUT/'LIVE_MODEL_RECEIPT.json').read_bytes()).hexdigest(),runtime_paid_allowed=False)
(OUT/'FINAL_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(dict(report_id=rid,checks=checks,source_files=len(files),build_id=manifest['build_id'])))
