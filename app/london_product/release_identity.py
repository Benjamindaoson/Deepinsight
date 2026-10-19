"""Public runtime identity contains no credentials or model configuration."""
import hashlib
import importlib.metadata
from pathlib import Path

_verified_release=None


def bind_verified_release(release):
    """Bind only the resolver-verified startup identity to the executing module."""
    global _verified_release
    if Path(release['backend_app']).resolve()!=Path(__file__).resolve().parents[1]:
        raise ValueError('Release identity does not match executing backend')
    digest=hashlib.sha256(Path(release['manifest_path']).read_bytes()).hexdigest()
    if digest!=release['manifest_sha256']:
        raise ValueError('Release manifest changed since startup validation')
    _verified_release=dict(release)


def runtime_identity(service, offline):
    value=dict(managed_release=False,release_id=None,manifest_sha256=None,frontend_build_id=None,
        source_app=str(Path(__file__).resolve().parents[1]),runtime_data=str(service.store.root),
        agno_version=importlib.metadata.version('agno'),mode='offline' if offline else 'live',
        workflow_ids=[getattr(getattr(service,name,None),'id',None) for name in ['workflow','report_workflow','query_workflow']],
        model_call_verified=False)
    if _verified_release:
        release=_verified_release
        digest=hashlib.sha256(Path(release['manifest_path']).read_bytes()).hexdigest()
        if digest!=release['manifest_sha256']:
            raise ValueError('Release manifest changed since startup validation')
        value.update(managed_release=True,release_id=release['release_id'],
            manifest_sha256=digest,frontend_build_id=release['frontend_build_id'])
    return value
