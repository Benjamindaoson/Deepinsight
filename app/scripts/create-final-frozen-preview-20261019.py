"""Materialize a reproducible source-only preview, with dummy model configuration."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/delivery/real-ai-frozen-20261019'
CANDIDATE = OUT / 'candidate'
RUNTIME = CANDIDATE / 'docs/delivery/runtime'
if CANDIDATE.exists():
    raise SystemExit('Refuse to overwrite frozen candidate')
CANDIDATE.mkdir(parents=True)
paths = []
for directory, patterns in {
    'app/london_product': ['*.py'], 'app/london_data': ['*.py'],
    'app/migrations': ['*.sql'], 'app/product_skills': ['*.md', '*.json', '*.yaml'],
    'app/tests': ['*.py'], 'app/frontend/src': ['*.ts', '*.tsx', '*.css'],
    'app/frontend/tests': ['*.mjs'],
}.items():
    for pattern in patterns:
        paths.extend(p for p in (ROOT / directory).rglob(pattern) if '__pycache__' not in p.parts)
paths.extend(ROOT / p for p in [
    'app/tests/fixtures/real_report_projection.json', 'app/scripts/run-isolated-product.py',
    'app/scripts/create-final-frozen-preview-20261019.py', 'app/pytest.ini',
    'app/requirements-product.lock.txt', 'app/requirements.lock.txt',
    'app/frontend/package.json', 'app/frontend/pnpm-lock.yaml', 'app/frontend/next.config.ts',
])
hashes = {}
for source in sorted(set(paths)):
    relative = source.relative_to(ROOT)
    destination = CANDIDATE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_bytes()
    destination.write_bytes(content)
    hashes[str(relative)] = hashlib.sha256(content).hexdigest()
# Detect modifications during the copy itself; do not silently mix generations.
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
(CANDIDATE / 'secrets').mkdir()
(CANDIDATE / 'secrets/model.json').write_text(json.dumps(dict(
    model='preview-disabled', api_key='DUMMY-NOT-A-CREDENTIAL', base_url='http://127.0.0.1:1/v1')), encoding='utf-8')
origin = ROOT / 'docs/delivery/real-ai-preview-20261019/runtime'
RUNTIME.mkdir(parents=True)
for name in ['market.sqlite3', 'agno.sqlite3']:
    with sqlite3.connect((origin / name).as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(RUNTIME / name) as dest:
            src.backup(dest)
shutil.copytree(origin / 'model-ledgers', RUNTIME / 'model-ledgers')
sys.path.insert(0, str(CANDIDATE / 'app'))
from london_product.store import Store
from london_product.chat_report import read_report
store = Store(RUNTIME)
before = {f['id']: (f.get('status'), f.get('human_review_status')) for f in store.all('facts')}
for document in store.all('documents'):
    source = Path(document['path'])
    content = source.read_bytes()
    assert hashlib.sha256(content).hexdigest() == document['sha256']
    destination = store.artifacts / (document['sha256'] + source.suffix)
    destination.write_bytes(content)
    store.update('documents', document['id'], dict(path=str(destination)))
assert before == {f['id']: (f.get('status'), f.get('human_review_status')) for f in store.all('facts')}
report = read_report(store, 'f9209186-901c-43cc-9f5b-6cc80df2fe99')
assert report['generation_status'] == 'partial'
assert report['ai_analysis']['status'] == 'published' and len(report['ai_analysis']['accepted']) == 2
assert sum(c['status'] == 'ready' for c in report['charts']) == 1
store.engine.dispose()
manifest = dict(candidate=str(CANDIDATE), runtime=str(RUNTIME), source_files=hashes,
    source_origin='Current developer source plus additive restoration projection; actual paid run belongs to its earlier audit source freeze',
    paid_run_source_manifest='docs/audit/deepseek-business-20261019-0450/SOURCE_MANIFEST.json',
    paid_calls=0, credential_config='Dummy localhost endpoint only; no original secrets copied',
    review_states_unchanged=True, report_id=report['report_id'])
(OUT / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(dict(source_files=len(hashes), candidate=str(CANDIDATE), report_status='partial', model_calls=0)))
