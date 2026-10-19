"""Canonical local release resolution, before importing candidate application code."""
import hashlib
import json
from pathlib import Path


def _inside(base, relative, label):
    if not isinstance(relative,str) or Path(relative).is_absolute():
        raise ValueError(label+' must be relative')
    path=(base/relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(label+' outside release')
    return path


def resolve_release(project_root, pointer_path=None):
    root=Path(project_root).resolve()
    pointer=Path(pointer_path) if pointer_path else root/'docs/delivery/ACTIVE_RELEASE.json'
    data=json.loads(pointer.read_text(encoding='utf-8-sig'))
    directory=_inside(root,data['directory'],'Release directory')
    manifest_path=directory/'FINAL_IDENTITY.json'
    digest=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest!=data['manifest_sha256']:raise ValueError('Release manifest hash mismatch')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['release_id']!=data['release_id']:raise ValueError('Release identity mismatch')
    for relative,expected in manifest['files'].items():
        path=_inside(directory,relative,'Manifest file')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Release file hash mismatch: '+relative)
    backend=_inside(directory,manifest['backend_app'],'Backend')
    frontend=_inside(directory,manifest['frontend'],'Frontend')
    build=_inside(frontend,manifest['build_dir'],'Build')
    if (build/'BUILD_ID').read_text().strip()!=manifest['frontend_build_id']:
        raise ValueError('Frontend build identity mismatch')
    return dict(release_id=manifest['release_id'],directory=str(directory),manifest_path=str(manifest_path),
        manifest_sha256=digest,backend_app=str(backend),frontend=str(frontend),build_dir=manifest['build_dir'],
        frontend_build_id=manifest['frontend_build_id'])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--pointer')
    options=parser.parse_args()
    print(json.dumps(resolve_release(Path(__file__).resolve().parents[1],options.pointer)))
