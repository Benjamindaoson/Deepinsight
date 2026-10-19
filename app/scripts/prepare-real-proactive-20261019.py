"""Actual source evidence probe, no model and no external notification."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,TABLES,now
from london_product.service import MarketService
OUT=ROOT/'docs/delivery/real-proactive-20261019';target=OUT/'runtime'
if target.exists():raise SystemExit('Preserve prior probe; runtime already exists')
origin=Store(ROOT/'docs/delivery/real-e2e-20261019/runtime');store=Store(target)
for table in ['sources','documents','facts','events','reports','settings','reviews']:
 for row in origin.all(table):
  if table=='documents':
   p=Path(row['path']);data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
   dest=store.artifacts/p.name;dest.write_bytes(data);row=dict(row,path=str(dest))
  store.put(table,row['id'],row)
origin.engine.dispose();svc=MarketService(store)
svc.agent_factory=lambda:(_ for _ in ()).throw(AssertionError('LIVE_MODEL_DISABLED'))
prior={f['id']:{k:f.get(k) for k in ['status','human_review_status']} for f in store.all('facts')}
(OUT/'review-baseline.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
config=svc.settings();result=svc.monitor_changes(detection_context='historical_replay')
old='07ded13f-ec67-40b8-a87d-faa66d017afe';new='a44bf53f-2f7c-4103-b04a-6a0e1212c156'
monitor_comparisons=[r for r in store.all('comparisons') if set(r.get('raw_input_ids',[]))=={old,new}]
explicit=svc.compare(old,new)
receipt=dict(at=now(),model_requests=0,notification_attempts=0,detection_context='historical_replay',vacancy_threshold_pp=config['vacancy_threshold_pp'],result=result,
 monitor_compared_reviewed_pair=bool(monitor_comparisons),explicit_real_comparison=explicit,
 pending_same_definition=[f['id'] for f in store.all('facts') if f.get('metric')=='vacancy' and f.get('geography')=='West End' and f.get('human_review_status')!='approved'])
(OUT/'INITIAL_MONITOR_PROBE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(monitor_compared_reviewed_pair=bool(monitor_comparisons),explicit_status=explicit['status'],explicit_change=explicit['absolute_change'],threshold=config['vacancy_threshold_pp'],alerts=result['alerts']),ensure_ascii=False))
svc.pool.shutdown(wait=True);store.engine.dispose()
