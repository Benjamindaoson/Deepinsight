"""Current free acquisition/parse on an isolated Store using production adapters.

No model/search requests, scheduling, notifications or live database mutations.
"""
import asyncio
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store
from london_product.service import MarketService
from london_product.sources import catalog,fetch_source,parse_content
from london_product.structured_sources import segments
OUT=Path(sys.argv[1]).resolve()
STORE=OUT/'isolated'
STORE.mkdir(exist_ok=True)
with sqlite3.connect(OUT/'backup/market.sqlite3') as src, sqlite3.connect(STORE/'market.sqlite3') as dst:src.backup(dst)
store=Store(STORE)
# Resolve old originals into the isolated artifact directory before any test.
for d in store.all('documents'):
    original=Path(d.get('path',''))
    if original.is_file():
        target=store.artifacts/original.name
        shutil.copy2(original,target)
        store.update('documents',d['id'],{'path':str(target)})
service=MarketService(store)
async def main():
    selected=[s for s in catalog() if s['id'] not in ['planning','knightfrank']]
    for s in selected:
        prior=store.get('sources',s['id'])
        if prior:store.update('sources',s['id'],dict({k:v for k,v in s.items() if k!='id'},etag=None,last_modified=None))
        else:store.put('sources',s['id'],s)
    sem=asyncio.Semaphore(2)
    async def one(s):
        async with sem:
            before={k:len(store.all(k)) for k in ['documents','facts','events']}
            stamp=datetime.now(timezone.utc).isoformat()
            if not s['enabled']:return dict(source_id=s['id'],at=stamp,status='blocked',reason=s['health'])
            try:
                result=await service.refresh(dict(source_id=s['id']))
                current=store.get('sources',s['id'])
                docs=[d for d in store.all('documents') if d['source_id']==s['id']]
                latest=docs[0] if docs else {}
                return dict(source_id=s['id'],at=stamp,status='acquired' if result.get('successes') else 'blocked',
                    result=result,health=current.get('health'),error=current.get('last_error'),
                    fields={k:latest.get(k) for k in ['id','url','sha256','media','published_at','collected_at']},
                    segments=len(latest.get('segments',[])),
                    after={k:len(store.all(k)) for k in before},before=before)
            except Exception as e:return dict(source_id=s['id'],at=stamp,status='blocked',error=type(e).__name__+': '+str(e)[:200])
    results=await asyncio.gather(*(one(s) for s in selected))
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),scope='Current production acquisition adapters into isolated SQLite clone; no paid calls',model_calls=0,search_calls=0,results=results)
    (OUT/'public-sources.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2,default=str))
asyncio.run(main())
