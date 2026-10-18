"""Capture official repository integrity, artifact inventory and secret leak check."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parents[2]
evidence=root/'b0/evidence'
repos=[]
for name in ('agent-ui','agno','agentos-docker'):
    path=root/'upstream'/name
    def git(*args):
        return subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True,encoding='utf-8')
    diff=git('diff','--exit-code','HEAD','--')
    # Check every tracked blob independently of checkout CRLF conversion.
    tree=subprocess.run(['git','-C',str(path),'ls-tree','-rz','HEAD'],capture_output=True,check=True).stdout
    entries=[]
    for item in tree.split(b'\0'):
        if not item:
            continue
        metadata,filename=item.split(b'\t',1)
        mode,kind,sha=metadata.split()
        if kind==b'blob':
            entries.append((mode,sha,filename.decode('utf-8')))
    blobs=subprocess.run(['git','-C',str(path),'cat-file','--batch'],input=b''.join(sha+b'\n' for _,sha,_ in entries),capture_output=True,check=True).stdout
    offset=0
    mismatches=[]
    eol_only=[]
    for mode,sha,filename in entries:
        end=blobs.index(b'\n',offset)
        size=int(blobs[offset:end].split()[-1])
        expected=blobs[end+1:end+1+size]
        offset=end+1+size+1
        file=path/filename
        if mode==b'120000':
            actual=os.readlink(file).encode('utf-8') if file.is_symlink() else file.read_bytes()
            actual=actual.replace(b'\\',b'/')
        else:
            actual=file.read_bytes()
        if actual!=expected:
            if b'\0' not in expected and actual.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n'):
                eol_only.append(filename)
            else:
                mismatches.append(filename)
    repos.append({'name':name,'sha':git('rev-parse','HEAD').stdout.strip(),
      'remote':git('remote','-v').stdout.strip(),'tracked_diff_exit':diff.returncode,
      'tracked_diff':diff.stdout,'status':git('status','--short').stdout.strip(),
      'tracked_blob_count':len(entries),'canonical_content_mismatches':mismatches,
      'checkout_line_endings_only':eol_only})
(evidence/'versions/repositories-final.json').write_text(json.dumps(repos,indent=2),encoding='utf-8')
keys=[v for k,v in os.environ.items() if ('API_KEY' in k or k.endswith('_TOKEN')) and len(v)>16]
for file in (root/'secrets').glob('*.json'):
    c=json.loads(file.read_text(encoding='utf-8-sig'))
    if c.get('api_key'):
        keys.append(c['api_key'])
findings=[]
files=[]
for folder in ('docs','scripts','smoke-tests','evidence','runtime-demo','openspec'):
    for file in (root/'b0'/folder).rglob('*'):
        if not file.is_file() or '__pycache__' in file.parts or file.suffix in ('.db','.pyc','.sqlite') or file.name.endswith(('.db-shm','.db-wal')):
            continue
        if file.name=='artifact-manifest.json':
            continue
        if file.suffix in ('.md','.txt','.log','.json','.jsonl','.ps1','.sh','.py','.tsv','.yaml'):
            content=file.read_text(encoding='utf-8-sig',errors='replace')
            if any(key in content for key in keys):
                findings.append(str(file.relative_to(root)))
        data=file.read_bytes()
        files.append({'path':file.relative_to(root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
summary={'captured_utc':datetime.now(timezone.utc).isoformat(),
 'official_tracked_sources_unchanged':all(r['tracked_diff_exit']==0 and not r['canonical_content_mismatches'] for r in repos),
 'secret_scan_findings':findings,'artifact_count':len(files),
 'live_log_note':'Hashes describe bytes at capture time. Running service logs and PID files may later change; live SQLite DB and environments are excluded.',
 'artifacts':files}
(evidence/'artifact-manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='artifacts'},indent=2))
raise SystemExit(0 if summary['official_tracked_sources_unchanged'] and not findings else 1)
