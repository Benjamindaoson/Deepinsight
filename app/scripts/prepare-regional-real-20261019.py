"""Inspect a new isolated baseline, preserving source originals and review states."""
import hashlib,json,shutil,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store
OUT=ROOT/'docs/delivery/regional-real-20261019';target=OUT/'runtime'
if target.exists():raise SystemExit('Preserve existing evidence; refusing overwrite')
target.mkdir(parents=True)
origin=ROOT/'docs/delivery/real-ai-frozen-20261019/candidate/docs/delivery/runtime'
for name in ['market.sqlite3','agno.sqlite3']:
 with sqlite3.connect((origin/name).as_uri()+'?mode=ro',uri=True) as src:
  with sqlite3.connect(target/name) as dst:src.backup(dst)
store=Store(target)
for d in store.all('documents'):
 data=Path(d['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==d['sha256']
 dest=store.artifacts/(d['sha256']+Path(d['path']).suffix);dest.write_bytes(data)
 store.update('documents',d['id'],dict(path=str(dest)))
facts=store.all('facts');baseline={f['id']:{k:f.get(k) for k in ['status','human_review_status']} for f in facts}
(OUT/'REVIEW_BASELINE.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
inventory=[]
for f in facts:
 if f.get('period') not in ['2026Q1','2026Q2']:continue
 if not any(g in f.get('geography','') for g in ['City','West End','Canary Wharf']):continue
 d=store.get('documents',f.get('document_id','')) or {}
 inventory.append(dict(fact=f,document={k:d.get(k) for k in ['id','url','sha256','path','published_at','title']}))
(OUT/'FACT_INVENTORY.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
for d in store.all('documents'):
 if '2026' in str(d.get('url','')) and 'pdf' in str(d.get('media','')):
  (OUT/(d['sha256'][:12]+'.pages.txt')).write_text('\n\n'.join('PAGE '+str(s.get('page'))+'\n'+s.get('text','') for s in d.get('segments',[])),encoding='utf-8')
print(json.dumps(dict(facts=len(facts),regional_candidates=len(inventory),documents=len(store.all('documents')),new_reviews=0,model_calls=0)))
store.engine.dispose()
