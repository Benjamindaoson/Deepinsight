"""Read-only source receipt and SQLite online backup; never initializes live Store."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/delivery' / ('poc-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(parents=True, exist_ok=False)
manifest = {}
for folder in ['app/london_product', 'app/london_data', 'app/tests', 'app/frontend/src', 'app/product_skills', 'app/migrations', 'app/scripts']:
    for path in (ROOT / folder).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            rel = path.relative_to(ROOT)
            data = path.read_bytes()
            dest = OUT / 'backup/source' / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            manifest[str(rel)] = dict(sha256=hashlib.sha256(data).hexdigest(), mtime_ns=path.stat().st_mtime_ns)
for filename in ['README.md', 'app/frontend/package.json', 'app/frontend/pnpm-lock.yaml', 'app/requirements-product.lock.txt']:
    path = ROOT / filename
    dest = OUT / 'backup/source' / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
counts = {}
for filename in ['market.sqlite3', 'agno.sqlite3']:
    source = ROOT / 'app/data/product' / filename
    dest = OUT / 'backup' / filename
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)
        if filename == 'market.sqlite3':
            for (table,) in src.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                counts[table] = src.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0]
git = {name: subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout for name, args in {
    'head': ['rev-parse', 'HEAD'], 'status': ['status', '--short'], 'submodules': ['submodule', 'status']}.items()}
receipt = dict(at=datetime.now(timezone.utc).isoformat(), source=manifest, git=git, live_counts=counts,
    backups={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT / 'backup').glob('*.sqlite3')},
    secret_files={p.name: dict(exists=True, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (ROOT / 'secrets').glob('*.json')},
    concurrency='No writer-stop assertion. Check each file against baseline immediately before editing; retain own post-edit hashes. Existing services untouched.')
(OUT / 'baseline.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(OUT)
print(json.dumps(dict(files=len(manifest), counts=counts, backup_hashes=receipt['backups']), indent=2))
