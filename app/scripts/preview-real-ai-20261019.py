"""Copy actual model acceptance data to a new, non-paying isolated preview."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from london_product.store import Store, now
from london_product.chat_report import read_report, render_markdown, render_html

ORIGIN = ROOT / 'docs/audit/deepseek-business-20261019-0450/live-runtime'
OUT = ROOT / 'docs/delivery/real-ai-preview-20261019'
TARGET = OUT / 'runtime'
REPORT_ID = 'f9209186-901c-43cc-9f5b-6cc80df2fe99'
if TARGET.exists():
    raise SystemExit('Preserve existing preview; refusing overwrite')
TARGET.mkdir(parents=True)
backups = {}
for name in ['market.sqlite3', 'agno.sqlite3']:
    source = ORIGIN / name
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(TARGET / name) as dest:
            src.backup(dest)
    backups[name] = hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
if (ORIGIN / 'model-ledgers').exists():
    shutil.copytree(ORIGIN / 'model-ledgers', TARGET / 'model-ledgers')
store = Store(TARGET)
review_fields = ['status', 'human_review_status']
before = {f['id']: {k: f.get(k) for k in review_fields} for f in store.all('facts')}
originals = []
for document in store.all('documents'):
    source = Path(document['path'])
    content = source.read_bytes()
    assert hashlib.sha256(content).hexdigest() == document['sha256']
    path = store.artifacts / (document['sha256'] + source.suffix)
    if path.exists():
        assert path.read_bytes() == content
    else:
        path.write_bytes(content)
    store.update('documents', document['id'], dict(path=str(path)))
    originals.append(dict(id=document['id'], sha256=document['sha256']))
after = {f['id']: {k: f.get(k) for k in review_fields} for f in store.all('facts')}
assert before == after
report = read_report(store, REPORT_ID)
analysis = report.get('ai_analysis') or {}
ready = [c for c in report['charts'] if c.get('status') == 'ready']
assert report['generation_status'] == 'partial'
assert analysis['status'] == 'published' and len(analysis['accepted']) == 2
assert not analysis['blocked'] and len(ready) == 1
assert all(e['evidence_integrity_status'] == 'verified' for e in report['evidence'])
markdown = render_markdown(report)
(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'report.md').write_text(markdown, encoding='utf-8')
(OUT / 'report.html').write_text(render_html(report), encoding='utf-8')
receipt = dict(at=now(), origin=str(ORIGIN), preview=str(TARGET), report_id=REPORT_ID,
    generation_status=report['generation_status'], ai_status=analysis['status'],
    accepted=len(analysis['accepted']), blocked=len(analysis['blocked']), ready_charts=len(ready),
    review_states_unchanged=before == after, copied_originals=originals,
    source_database_snapshot_sha256=backups, model_calls=0,
    public_url='http://localhost:3105/reports?report=' + REPORT_ID,
    runtime_policy=dict(paid_allowed=False, scheduler=False, notifications=False))
(OUT / 'PREVIEW_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
store.engine.dispose()
print(json.dumps({k: receipt[k] for k in ['report_id', 'generation_status', 'ai_status', 'accepted', 'blocked', 'ready_charts', 'review_states_unchanged', 'model_calls']}))
