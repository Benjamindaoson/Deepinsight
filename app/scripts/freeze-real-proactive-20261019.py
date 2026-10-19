"""Freeze final source and verify read-only preview endpoints. Never call a model."""
import hashlib,json,sys
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import now
OUT=ROOT/'docs/delivery/real-proactive-20261019'
identity=requests.get('http://localhost:7785/api/market/runtime-identity',timeout=15).json()
assert identity['paid_allowed'] is False and identity['scheduler'] is False and identity['notifications'] is False
assert Path(identity['directory']).resolve()==(OUT/'runtime').resolve()
for name,sha in identity['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha
checks=[]
rid='b815e22e-459d-437a-adbc-e22ccecd4a4d'
for path in ['/health','/api/market/reports','/api/market/notifications','/api/market/reports/'+rid+'?format=json','/api/market/reports/'+rid+'?format=markdown']:
 response=requests.get('http://localhost:7785'+path,timeout=15);assert response.status_code==200
 checks.append(dict(path=path,status=200,sha256=hashlib.sha256(response.content).hexdigest()))
 if path.endswith('format=markdown'):
  assert 'vacancy · West End: 2026Q1 → 2026Q2 = -0.10 pp' in response.text
files=[p for folder in ['app/london_product','app/london_data','app/tests'] for p in (ROOT/folder).glob('*.py')]
files += [ROOT/'app/.env.product.example']+list((ROOT/'openspec/changes/real-proactive-evidence-acceptance').rglob('*.md'))
files += [ROOT/'app/scripts'/n for n in ['prepare-real-proactive-20261019.py','accept-real-proactive-20261019.py','freeze-real-proactive-20261019.py']]
for p in files:
 q=OUT/'source-freeze'/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
manifest=dict(at=now(),source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},runtime=identity,http_checks=checks,
 verification=dict(full_backend='521 passed; before final calibration-cap validation delta',final_targeted='50 passed after cap validation',frontend='unchanged from verified build KUDDyxuBlCfGJEK7eDdoS'),
 model_requests_by_developer=0,review_state_changes=0,real_notification_recipients=0,significant_proactive_ai_business='NOT_PASSED')
(OUT/'FINAL_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(files=len(files),runtime_pid=identity['pid'],http_checks=checks,paid_allowed=False)))
