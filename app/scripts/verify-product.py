"""Local real-data read/performance/integrity and transaction-interruption probe.
Never calls a model, external source or notification channel.
"""
import hashlib,json,statistics,subprocess,sys,time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_product.store import Store
from london_product.service import MarketService

APP=Path(__file__).resolve().parents[1];ROOT=APP.parent;DATA=APP/'data/product';OUT=DATA/'evidence'
OUT.mkdir(parents=True,exist_ok=True)


def dump(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def samples(call,count=30):
    values=[]
    for _ in range(count):
        t=time.perf_counter();call();values.append((time.perf_counter()-t)*1000)
    return dict(count=count,p50_ms=statistics.median(values),p95_ms=sorted(values)[int(.95*(count-1))],max_ms=max(values),samples_ms=values)


def main():
    store=Store(DATA);service=MarketService(store);client=httpx.Client(base_url='http://127.0.0.1:7780',timeout=20,trust_env=False)
    overview=client.get('/api/market/overview');overview.raise_for_status();dump('final-overview.json',overview.json())
    performance={'cached_http_facts':samples(lambda:client.get('/api/market/facts?limit=100').raise_for_status())}
    def uncached():service.invalidate();service.facts(limit=100)
    performance['uncached_sql_facts']=samples(uncached)
    performance['saved_deterministic_compare']=samples(lambda:client.post('/api/market/compare',json={'old_id':'BNP-2026Q1-VACANCY','new_id':'BNP-2026Q2-VACANCY'}).raise_for_status())
    from london_product.sources import parse_content
    document=next(d for d in store.all('documents') if d['id']=='doc-bnp-8255a921c15294718433')
    performance['pdf_parse']=samples(lambda:parse_content(Path(document['path']).read_bytes(),document['media']),count=3)
    models=[j for j in store.all('jobs') if j.get('kind')=='ask' and j.get('run_id')]
    performance['actual_agent_runs']=[{k:j.get(k) for k in ['id','status','run_id','metrics','quality_status']} for j in models]
    performance['actual_extractions']=[{k:e.get(k) for k in ['id','status','run_id','budget']} for e in store.all('extractions')]
    performance['workflow_jobs']=[{k:j.get(k) for k in ['id','kind','status','started_at','finished_at','run_id','result']} for j in store.all('jobs') if j.get('kind')!='ask']
    dump('performance.json',performance)
    # A real subprocess writes inside BEGIN IMMEDIATE, is killed before COMMIT,
    # and SQLite must roll it back while preserving all pre-existing facts.
    before=store.all('facts');marker='__product_transaction_interrupt__'
    child_code="import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"INSERT INTO jobs(id,identity,payload) VALUES(?,?,?)\",(sys.argv[2],sys.argv[2],'{}'));print('transaction-written',flush=True);time.sleep(120)"
    child=subprocess.Popen([sys.executable,'-c',child_code,str(DATA/'market.sqlite3'),marker],stdout=subprocess.PIPE,text=True)
    try:
        signal=child.stdout.readline().strip();assert signal=='transaction-written'
        child.terminate();child.wait(timeout=10)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=10)
    assert store.get('jobs',marker) is None
    assert before==store.all('facts')
    dump('write-interruption.json',dict(process_exit=child.returncode,signal=signal,uncommitted_row_absent=True,facts_unchanged=True,fact_count=len(before)))
    frozen=json.loads((OUT/'protected-baseline.json').read_text(encoding='utf-8-sig'));differences=[]
    for relative,expected in frozen.items():
        path=ROOT/relative
        actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual!=expected:differences.append(dict(path=relative,expected=expected,actual=actual))
    dump('protected-integrity.json',dict(checked=len(frozen),differences=differences))
    assert not differences
    package={table:store.all(table) for table in ['sources','documents','facts','comparisons','events','jobs','extractions','reports','notifications']}
    package['quality_notice']='Original human review remains pending; no formal B1 PASS. Native failures and incomplete usage retained.'
    dump('result-package.json',package)
    dump('original-hashes.json',[{k:d.get(k) for k in ['id','sha256','path','url','published_at','collected_at']} for d in store.all('documents')])
    print(json.dumps({'status':'PASS','protected_files':len(frozen),'fact_versions':len(before),'active_candidate_facts':len(service.facts(limit=500)['items']),'performance':{k:v for k,v in performance.items() if isinstance(v,dict)}}))


if __name__=='__main__':main()
