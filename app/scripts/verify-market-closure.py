"""Local saved-source verification; no model requests or fact approvals."""
import hashlib
import json
import time
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from london_product.store import Store
from london_product.service import MarketService
from london_product.qa_context import evidence_pack

APP = Path(__file__).resolve().parents[1]
OUT = APP/'data/product/evidence/market-closure-20261018'
OUT.mkdir(parents=True,exist_ok=True)


def dump(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def main():
    store=Store(APP/'data/product'); service=MarketService(store)
    originals={d['id']: dict(sha256=d['sha256'],actual=hashlib.sha256(Path(d['path']).read_bytes()).hexdigest()) for d in store.all('documents')}
    assert all(v['sha256']==v['actual'] for v in originals.values())
    dump('originals.json',originals)
    dump('facts-after.json',store.all('facts'))
    changes=[e for e in store.all('events') if e.get('classification')=='publisher_reported_change']
    assert changes and all(e.get('run_id') for e in changes), 'Native monitoring workflow must create the source change first'
    dump('market-change-case.json',changes)
    assert all(not e['calculation_performed'] and e['human_review_status']=='pending_review' for e in changes)
    pack=evidence_pack(service,'最近一个季度伦敦写字楼市场有哪些变化、风险和机会？',dict(facts=[],events=[]))
    dump('preflight-evidence-pack.json',pack)
    timings=[]
    with httpx.Client(base_url='http://127.0.0.1:7780',trust_env=False,timeout=20) as client:
        for _ in range(20):
            started=time.perf_counter();r=client.get('/api/market/facts');r.raise_for_status()
            timings.append((time.perf_counter()-started)*1000)
        started=time.perf_counter()
        r=client.post('/api/market/compare',json=dict(old_id='BNP-2026Q1-TAKEUP',new_id='BNP-2026Q2-TAKEUP'));r.raise_for_status()
        comparison=r.json()
        assert comparison['status']=='not_comparable' and comparison['absolute_change'] is None
        dump('strict-comparison.json',dict(result=comparison,elapsed_ms=(time.perf_counter()-started)*1000))
        response=client.post('/api/market/reports',json=dict(period='weekly',include_analysis=False),headers={'Idempotency-Key':'market-closure-20261018-weekly'})
        response.raise_for_status();report=response.json();assert report.get('workflow_run_id')
        duplicate=client.post('/api/market/reports',json=dict(period='weekly',include_analysis=False),headers={'Idempotency-Key':'market-closure-20261018-weekly'}).json()
        assert duplicate['id']==report['id']
        dump('weekly-report.json',report)
        for fmt,ext in [('markdown','md'),('html','html')]:
            export=client.get('/api/market/reports/'+report['id'],params={'format':fmt});export.raise_for_status()
            assert 'publisher_reported_change' in export.text and '15%' in export.text
            (OUT/('weekly-report.'+ext)).write_text(export.text,encoding='utf-8')
    dump('performance.json',dict(observations=len(timings),query_http_ms=timings,p95_ms=sorted(timings)[18],
        limitation='Local sequential sample, not production SLA; first request may be cached.',new_model_requests=0))
    before=OUT/'facts-before.json'
    if before.exists():
        old=json.loads(before.read_text(encoding='utf-8'))
        assert all(store.get('facts',f['id'])==f for f in old), 'Pre-existing fact changed'
    service.pool.shutdown(wait=True)
    print(json.dumps(dict(status='PASS',publisher_changes=len(changes),report_id=report['id'],model_requests=0)))


if __name__=='__main__':main()
