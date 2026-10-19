"""Freeze source/build identity after successful build, before any browser acceptance."""
import datetime
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/delivery/unified-release-20261019-r1'
front=OUT/'accepted-frontend';build=front/'.next-unified'
assert (build/'BUILD_ID').is_file()
files={}
for parent in [OUT/'accepted-backend/app',front]:
    import os
    for directory,dirs,names in os.walk(parent,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','cache'] and not d.startswith('.next-') or d=='.next-unified']
        for name in names:
            path=pathlib.Path(directory)/name
            if path.suffix in ['.pyc','.tsbuildinfo','.log'] or name in ['trace']:continue
            files[path.relative_to(OUT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
manifest=dict(release_id=OUT.name,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    backend_app='accepted-backend/app',frontend='accepted-frontend',build_dir='.next-unified',
    frontend_build_id=(build/'BUILD_ID').read_text().strip(),files=files,
    official_frontend='http://127.0.0.1:3105',official_api='http://127.0.0.1:7788',
    actual_runtime_database=str(ROOT/'app/data/product'),
    features=['audited_skill_load_before_search','personal_model_vault','owner_scoped_attachments','native_saved_query_and_research_workflows'],
    safety=dict(scheduler=False,automatic_monitoring=False,notifications=False,paid_search=False))
path=OUT/'FINAL_IDENTITY.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
pointer=dict(release_id=OUT.name,directory=str(OUT.relative_to(ROOT).as_posix()),
    manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(OUT/'CANDIDATE_POINTER.json').write_text(json.dumps(pointer,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(release_id=OUT.name,manifest_sha256=pointer['manifest_sha256'],files=len(files),build_id=manifest['frontend_build_id'])))
