"""Create a fresh coherent candidate; dependencies remain in the project environment."""
import datetime
import hashlib
import json
import pathlib
import shutil
import sqlite3

ROOT=pathlib.Path(__file__).resolve().parents[1]
NAME='unified-release-20261019-r1'
OUT=ROOT/'docs/delivery'/NAME


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    OUT.mkdir(exist_ok=False)
    app=OUT/'accepted-backend/app';app.mkdir(parents=True)
    for name in ['london_product','london_data','product_skills','migrations','docs/product']:
        shutil.copytree(ROOT/'app'/name,app/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ['requirements-product.lock.txt','.env.product.example']:
        shutil.copy2(ROOT/'app'/name,app/name)
    front=OUT/'accepted-frontend'
    shutil.copytree(ROOT/'app/frontend',front,ignore=shutil.ignore_patterns('node_modules','.next*','__pycache__','.env.local','.env.production.local','tsconfig.tsbuildinfo','*.log'))
    baseline={str(p.relative_to(OUT).as_posix()):digest(p) for base in [app,front] for p in base.rglob('*') if p.is_file()}
    (OUT/'SOURCE_BASELINE.json').write_text(json.dumps(dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=baseline),indent=2)+'\n',encoding='utf-8')
    private=ROOT/'secrets'/NAME;private.mkdir(exist_ok=False)
    for name in ['market.sqlite3','agno.sqlite3']:
        original=ROOT/'app/data/product'/name
        with sqlite3.connect(original.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(private/name) as target:source.backup(target)
    (OUT/'PREVIOUS_ACTIVE_POINTER.txt').write_text((ROOT/'docs/delivery/ACTIVE_CHAT_MODELS_DELIVERY.txt').read_text(),encoding='utf-8')
    print(json.dumps(dict(candidate=str(OUT),source_files=len(baseline),database_backup='Git-ignored secrets/'+NAME,model_requests=0)))


if __name__=='__main__':freeze()
