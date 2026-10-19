"""Snapshot real evidence; refresh connected research sources without reviewing facts."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from london_product.store import Store, now
from london_product.service import MarketService
from london_product.sources import catalog

OUT = ROOT / 'docs/delivery/institutional-report-acceptance'
OUT.mkdir(exist_ok=True)
TARGET = OUT / 'runtime'
if TARGET.exists():
    raise SystemExit('Preserve existing acceptance; directory already exists.')
source = Store(ROOT / 'app/data/product')
store = Store(TARGET)
baseline = {}
for table in ['sources', 'documents', 'facts', 'events']:
    rows = source.all(table)
    for row in rows:
        if table in ['facts', 'events']:
            baseline[table + ':' + row['id']] = {k: row.get(k) for k in ['status', 'human_review_status']}
        if table == 'documents':
            path = Path(row.get('path', ''))
            if path.is_file() and path.resolve().is_relative_to(ROOT):
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() == row.get('sha256'):
                    target = store.artifacts / (row['sha256'] + path.suffix)
                    if not target.exists(): target.write_bytes(content)
                    row = dict(row, path=str(target))
        store.put(table, row['id'], row)
(OUT / 'review-baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
service = MarketService(store)

async def main():
    results = []
    for item in catalog():
        if item['id'] not in ['bnp', 'jll', 'savills', 'savills-html', 'cbre']: continue
        prior = store.get('sources', item['id'])
        if prior:
            # Keep access policy, human decisions and source identity intact.
            item = store.update('sources', item['id'], dict(url=item['url'], etag=None, last_modified=None))
        else: item = store.put('sources', item['id'], item)
        results.append(dict(source_id=item['id'], result=await service.refresh(dict(source_id=item['id']))))
    config = json.loads((ROOT / 'secrets/model.json').read_text(encoding='utf-8-sig'))
    receipt = dict(at=now(), model=config['model'], source_results=results, model_calls=0,
                   counts={t: len(store.all(t)) for t in ['sources','documents','facts','events']})
    changes = []
    for key, original in baseline.items():
        table, identity = key.split(':', 1)
        current = store.get(table, identity)
        if {k: current.get(k) for k in original} != original: changes.append(key)
    receipt['existing_review_state_changes'] = changes
    (OUT / 'source-refresh.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, default=str))
    service.pool.shutdown(wait=False)

asyncio.run(main())
