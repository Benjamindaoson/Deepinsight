"""Clone public market evidence into a repository-local isolated acceptance Store."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store

target=ROOT/'docs/delivery/chat-report-acceptance/runtime'
if target.exists():raise SystemExit('Acceptance directory exists; preserve it and select a new run explicitly.')
source=Store(ROOT/'app/data/product')
destination=Store(target)
counts={}
for table in ['sources','documents','facts','events']:
    rows=source.all(table)
    for row in rows:
        if table=='documents':
            original=Path(row.get('path','')).resolve()
            if original.is_file() and original.is_relative_to(ROOT):
                data=original.read_bytes()
                if hashlib.sha256(data).hexdigest()==row.get('sha256'):
                    output=destination.artifacts/(row['sha256']+original.suffix)
                    if not output.exists():output.write_bytes(data)
                    row=dict(row,path=str(output))
        destination.put(table,row['id'],row)
    counts[table]=len(rows)
receipt=dict(source=str(source.root),destination=str(target),counts=counts,
    models_called=0,source_facts_modified=False,note='Copied real saved observations without changing review status. Missing evidence remains missing.')
(target.parent/'preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
