"""Immutable continuation candidate; preserve the independently tested v2."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/delivery/regional-real-20261019'
base=json.loads((OUT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
candidate=OUT/'candidate-v5'
if candidate.exists():raise SystemExit('Do not overwrite a real-acceptance candidate')
paths=set(base['source_files'])|{'app/scripts/freeze-regional-continuation-20261019.py'}
for directory in ['london_product','london_data','tests','product_skills']:
    for source in (ROOT/'app'/directory).rglob('*'):
        if source.is_file() and source.suffix in ['.py','.md','.yaml','.json'] and '__pycache__' not in source.parts:
            paths.add(str(source.relative_to(ROOT)))
hashes={}
for path in sorted(paths):
    source=ROOT/path;destination=candidate/path
    destination.parent.mkdir(parents=True,exist_ok=True)
    content=source.read_bytes();destination.write_bytes(content)
    hashes[path]=hashlib.sha256(content).hexdigest()
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(candidate/'secrets').mkdir()
(candidate/'secrets/model.json').write_text(json.dumps(dict(model='preview-disabled',api_key='DUMMY-NOT-A-CREDENTIAL',base_url='http://127.0.0.1:1/v1')),encoding='utf-8')
manifest=dict(base,candidate=str(candidate),source_files=hashes,parent_manifest_sha256=hashlib.sha256((OUT/'SOURCE_MANIFEST.json').read_bytes()).hexdigest(),
    revision='v5: dependency closure and runnable dummy model configuration; async native service entry preserving ContextVars; original question in HTML/Markdown; compatibility fixes',
    real_execution='Independent owner: preserve regional real result from v2, run only corrected proactive scenario against this candidate',
    async_regression='8 passed; includes sync scheduler and already-running event loop, context preservation and no duplicate execution')
path=OUT/'SOURCE_MANIFEST_V5.json'
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
ready=dict(manifest_path=str(path),manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),candidate=str(candidate),
    runtime=base['qualified_runtime'],old_preview_untouched=True,new_preview_ports=dict(api=7786,frontend=3106))
(OUT/'CANDIDATE_PENDING_SMOKE.json').write_text(json.dumps(ready,indent=2),encoding='utf-8')
print(json.dumps(ready))
