"""Consistent local SQLite backups and hashes; no publishing or secret copying."""
import sqlite3,json,hashlib,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.extraction import ROOT

dest=ROOT/'b1/delivery';dest.mkdir(exist_ok=True)
for name in ['market.db','agno.db']:
    source=ROOT/'b1/data'/name;target=dest/name
    with sqlite3.connect('file:'+source.as_posix()+'?mode=ro',uri=True) as src,sqlite3.connect(str(target)) as dst:src.backup(dst)
logs=dest/'runtime-logs';logs.mkdir(exist_ok=True)
for p in (ROOT/'b1/evidence/logs').glob('*.log'):shutil.copy2(p,logs/p.name)
files={}
for base in [ROOT/'app',ROOT/'b1']:
    for p in base.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ['.venv','__pycache__','.pytest_cache','.codegraph','node_modules']):continue
        if p.name=='manifest.json' and p.parent==dest:continue
        if p.parent==ROOT/'b1/data' and (p.suffix=='.db' or p.name.endswith(('-wal','-shm'))):continue
        if p.name.endswith('.pid') or ROOT/'b1/evidence/logs' in p.parents:continue
        files[str(p.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(p.read_bytes()).hexdigest()
report={'created_at':datetime.now(timezone.utc).isoformat(),'source_root':str(ROOT),'scope':'B1 local audit delivery; not licensed for public redistribution. Live DB/WAL/PIDs and active runtime logs excluded; consistent DB backups and frozen log copies included. No secrets directory copied.','files':files}
(dest/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in files.items())
print(json.dumps({'files':len(files),'manifest':str(dest/'manifest.json'),'database_backups':['market.db','agno.db']},indent=2))
