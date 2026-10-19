"""Freeze source only, never credentials/data; execute separately before probes."""
import hashlib
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'docs/delivery/claim-evidence-binding-phase1')
OUT = parser.parse_args().output.resolve()
if not OUT.is_relative_to(ROOT / 'docs/delivery'):
    parser.error('Candidate must stay under repository docs/delivery.')
CANDIDATE = OUT / 'candidate'
paths = sorted({
    *ROOT.glob('app/london_product/*.py'), *ROOT.glob('app/london_product/*.json'),
    *ROOT.glob('app/london_data/*.py'), *ROOT.glob('app/london_data/*.json'),
    *ROOT.glob('app/migrations/*.sql'),
})
if (OUT / 'SOURCE_MANIFEST.json').exists():
    raise SystemExit('Existing frozen manifest: use a new candidate directory, never overwrite.')
files = []
for source in paths:
    relative = source.relative_to(ROOT)
    target = CANDIDATE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    copied = hashlib.sha256(target.read_bytes()).hexdigest()
    assert digest == copied
    files.append(dict(path=relative.as_posix(), sha256=digest, copy_sha256=copied))
probe = ROOT / 'docs/audit/claim-evidence-reacceptance-20261018-2300/phase1_probes.py'
shutil.copy2(probe, OUT / 'phase1_probes.py')
manifest = dict(at=datetime.now(timezone.utc).isoformat(),
    purpose='Phase 1 frozen source candidate; synthetic probes only; no market approvals',
    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    git_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
    probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),files=files)
(OUT / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(dict(candidate=str(CANDIDATE), files=len(files), probe_sha256=manifest['probe_sha256'])))
