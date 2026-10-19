"""Real-file release guards and real native workflow persistence; no provider transport."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]


def helper():
    path=ROOT/'scripts/release_manifest.py'
    assert path.is_file(), 'Official startup lacks verified release resolution'
    spec=importlib.util.spec_from_file_location('release_manifest_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def release_tree(tmp_path):
    folder=tmp_path/'docs/delivery/accepted'
    backend=folder/'accepted-backend/app/london_product/runtime.py'
    backend.parent.mkdir(parents=True);backend.write_text('accepted code\n')
    build=folder/'accepted-frontend/.next-unified/BUILD_ID'
    build.parent.mkdir(parents=True);build.write_text('verified-build')
    manifest=folder/'FINAL_IDENTITY.json'
    manifest.write_text(json.dumps(dict(release_id='test-release',backend_app='accepted-backend/app',
        frontend='accepted-frontend',build_dir='.next-unified',frontend_build_id='verified-build',
        files={str(p.relative_to(folder).as_posix()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [backend,build]})))
    pointer=tmp_path/'docs/delivery/ACTIVE_RELEASE.json'
    pointer.write_text(json.dumps(dict(directory='docs/delivery/accepted',release_id='test-release',
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())))
    return folder,backend,manifest,pointer


def test_changed_frozen_backend_refuses_startup(tmp_path):
    module=helper();folder,backend,manifest,pointer=release_tree(tmp_path)
    valid=module.resolve_release(tmp_path)
    assert valid['release_id']=='test-release'
    backend.write_text('unaccepted changed code\n')
    with pytest.raises(ValueError,match='hash mismatch'):
        module.resolve_release(tmp_path)


def test_unaccepted_manifest_and_escaped_paths_refuse_startup(tmp_path):
    module=helper();folder,backend,manifest,pointer=release_tree(tmp_path)
    data=json.loads(manifest.read_text());data['files']['../../outside.py']='0'*64
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='manifest hash mismatch'):
        module.resolve_release(tmp_path)
    p=json.loads(pointer.read_text());p['manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest();pointer.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='outside release'):
        module.resolve_release(tmp_path)


def test_wrong_production_build_refuses_startup(tmp_path):
    module=helper();folder,backend,manifest,pointer=release_tree(tmp_path)
    data=json.loads(manifest.read_text());data['frontend_build_id']='another-build';manifest.write_text(json.dumps(data))
    p=json.loads(pointer.read_text());p['manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest();pointer.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='build identity mismatch'):
        module.resolve_release(tmp_path)


def test_unmanaged_runtime_does_not_claim_frozen_release(tmp_path):
    from london_product.runtime import create_app
    with TestClient(create_app(tmp_path,seed=False,scheduler=False,offline=True)) as client:
        response=client.get('/api/market/release')
    assert response.status_code==200
    assert response.json()['managed_release'] is False
    assert response.json()['release_id'] is None


def test_saved_query_job_persists_actual_native_workflow_links(tmp_path):
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json=dict(mode='saved',message='Explain London office market changes and risks in 2026Q2.'))
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    done=next(e for e in events if e.get('type')=='done')
    job=app.state.market.store.get('jobs',done['submission_id'])
    assert len(job.get('workflow_run_ids',[]))==2,'Submission loses the real scope/report Workflow IDs'
    assert job['workflow_run_ids']==done['workflow_run_ids']


def test_manifest_environment_alone_cannot_claim_accepted_source(tmp_path,monkeypatch):
    from london_product import release_identity
    _,_,manifest,_=release_tree(tmp_path)
    monkeypatch.setenv('LONDON_RELEASE_MANIFEST',str(manifest))
    monkeypatch.setattr(release_identity,'_verified_release',None,raising=False)
    from types import SimpleNamespace
    identity=release_identity.runtime_identity(SimpleNamespace(store=SimpleNamespace(root=tmp_path)),False)
    assert identity['managed_release'] is False


def test_verified_identity_rejects_wrong_source_and_manifest_replacement(tmp_path,monkeypatch):
    from london_product import release_identity
    _,_,manifest,_=release_tree(tmp_path)
    verified=helper().resolve_release(tmp_path)
    monkeypatch.setattr(release_identity,'_verified_release',None,raising=False)
    with pytest.raises(ValueError,match='executing backend'):
        release_identity.bind_verified_release(verified)
    verified['backend_app']=str(Path(release_identity.__file__).resolve().parents[1])
    release_identity.bind_verified_release(verified)
    from types import SimpleNamespace
    service=SimpleNamespace(store=SimpleNamespace(root=tmp_path))
    assert release_identity.runtime_identity(service,False)['managed_release'] is True
    manifest.write_text('{}')
    with pytest.raises(ValueError,match='changed since startup'):
        release_identity.runtime_identity(service,False)
