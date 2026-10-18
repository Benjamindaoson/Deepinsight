"""Restore only proven CRLF-only checkout differences to exact official HEAD bytes."""
import hashlib
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
repo=root/'upstream/agent-ui'
previous=json.loads((root/'b0/evidence/versions/repositories-final.json').read_text(encoding='utf-8'))
row=next(r for r in previous if r['name']=='agent-ui')
if row['canonical_content_mismatches']:
    raise RuntimeError('Non-EOL modifications exist; refusing to overwrite')
receipt=[]
for name in row['checkout_line_endings_only']:
    path=(repo/name).resolve()
    if not path.is_relative_to(repo.resolve()):
        raise RuntimeError('Path escaped official clone')
    actual=path.read_bytes()
    expected=subprocess.check_output(['git','-C',str(repo),'show',f'HEAD:{name}'])
    if actual.replace(b'\r\n',b'\n')!=expected.replace(b'\r\n',b'\n'):
        raise RuntimeError(f'Content changed since audit: {name}; refusing to overwrite')
    path.write_bytes(expected)
    receipt.append({'path':name,'before_sha256':hashlib.sha256(actual).hexdigest(),
        'after_sha256':hashlib.sha256(expected).hexdigest(),'action':'Restore exact HEAD blob after proving checkout differences are only CRLF'})
(root/'b0/evidence/versions/checkout-eol-restoration.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('Restored exact official HEAD bytes for',len(receipt),'CRLF-only files; no semantic edits.')
