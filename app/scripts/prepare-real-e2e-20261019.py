"""Refresh public research in a new isolated Store; never approve a fact."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.service import MarketService

OUT=ROOT/'docs/delivery/real-e2e-20261019'
TARGET=OUT/'runtime'
if TARGET.exists():raise SystemExit('Preserve existing acceptance store; use a new directory.')
source=Store(ROOT/'docs/delivery/institutional-report-acceptance/runtime')
store=Store(TARGET);baseline={}
for table in ['sources','documents','facts','events']:
    for row in source.all(table):
        if table in ['facts','events']:baseline[table+':'+row['id']]={k:row.get(k) for k in ['status','human_review_status']}
        if table=='documents':
            path=Path(row.get('path',''))
            if path.is_file() and path.resolve().is_relative_to(ROOT):
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()==row.get('sha256'):
                    target=store.artifacts/(row['sha256']+path.suffix)
                    if not target.exists():target.write_bytes(data)
                    row=dict(row,path=str(target))
        store.put(table,row['id'],row)
(OUT/'review-baseline.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
source.engine.dispose()
service=MarketService(store)
new_sources=[
 ('savills-q2-public','Savills Central London Q2 2026 public research','https://www.savills.co.uk/research_articles/229130/393427-0/central-london-office-market-watch-q2-2026'),
 ('colliers-q2-public','Colliers London Offices Snapshot July 2026','https://www.colliers.com/en-gb/research/london-offices-snapshot-july-2026'),
 ('carter-jonas-q2-public','Carter Jonas Q2 2026 net effective rents','https://www.carterjonas.co.uk/insights/central-london-net-effective-rents-monitor-q2-2026'),
]
for identity,name,url in new_sources:
    store.put('sources',identity,dict(id=identity,name=name,url=url,kind='web_report',category='research',enabled=True,allow_llm=True))

async def main():
    results=[]
    for identity in ['bnp','jll']+[s[0] for s in new_sources]:
        row=store.get('sources',identity)
        if not row:continue
        store.update('sources',identity,dict(etag=None,last_modified=None))
        result=await service.refresh(dict(source_id=identity))
        results.append(dict(source_id=identity,result=result))
    changes=[]
    for key,before in baseline.items():
        table,identity=key.split(':',1);current=store.get(table,identity)
        if not current or {k:current.get(k) for k in before}!=before:changes.append(key)
    receipt=dict(at=now(),source_results=results,existing_review_state_changes=changes,model_calls=0,
        counts={t:len(store.all(t)) for t in ['sources','documents','facts','events']})
    (OUT/'source-refresh.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,default=str))
    assert not changes
try:asyncio.run(main())
finally:
    service.pool.shutdown(wait=True);store.engine.dispose()
