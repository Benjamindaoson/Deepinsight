"""Compare this working copy with the preserved pre-edit archive, without Git."""
from pathlib import Path
import zipfile, difflib, json

root = Path(__file__).parents[2]
frontend = root / 'app/frontend'
out = root / 'docs/ux/evidence'
with zipfile.ZipFile(out / 'before-source.zip') as archive:
    old = {name: archive.read(name) for name in archive.namelist()}
paths = set(old) | {p.relative_to(frontend).as_posix() for p in (frontend / 'src').rglob('*') if p.is_file()} | {p.relative_to(frontend).as_posix() for p in (frontend / 'tests').rglob('*') if p.is_file()}
changes, patches = [], []
for name in sorted(paths):
    path = frontend / name
    before = old.get(name, b'')
    after = path.read_bytes() if path.is_file() else b''
    if before != after:
        changes.append(name)
        patches.extend(difflib.unified_diff(before.decode('utf-8-sig', errors='replace').splitlines(True), after.decode('utf-8-sig', errors='replace').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
(out / 'changed-files.json').write_text(json.dumps(changes, indent=2), encoding='utf-8')
(out / 'source-diff.patch').write_text(''.join(patches), encoding='utf-8')
print('\n'.join(changes))
