"""Replay saved failures and verify the running product, without model/network research.

Only loopback HTTP is used. The strict comparison endpoint may persist its result;
all source/fact/event/extraction/original report records must remain unchanged.
"""
import hashlib
import json
import sys
import time
from pathlib import Path
import httpx
import fitz
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from london_product.store import Store
from london_product.analysis_guard import review_analysis, event_context, source_inventory

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DATA = APP/'data/product'
OUT = DATA/'evidence/final-repair-20261018'


def dump(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def main():
    store = Store(DATA)
    replay = []
    for version in ['v1','v2']:
        path = DATA/f'evidence/ai-report-analysis-{version}.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        result = review_analysis(original['result']['answer'], store)
        assert result['publication_review']['status'] == 'withheld'
        replay.append(dict(version=version, original_run_id=original['run_id'],
            original_file=str(path), original_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            new_model_requests=0, **result))
        (OUT/f'{version}-safe-publication.md').write_text(result['answer'], encoding='utf-8')
    dump('real-output-replay.json', replay)
    with httpx.Client(base_url='http://127.0.0.1:7780', timeout=20, trust_env=False) as client:
        start=time.perf_counter()
        response=client.post('/api/market/compare',json=dict(old_id='BNP-2026Q1-TAKEUP',new_id='BNP-2026Q2-TAKEUP'))
        response.raise_for_status(); comparison=response.json()
        assert comparison['status']=='not_comparable' and comparison['absolute_change'] is None
        assert 'HUMAN_REVIEW_PENDING' in comparison['reasons']
        dump('real-comparison.json',dict(result=comparison,elapsed_ms=(time.perf_counter()-start)*1000,model_requests=0))
        report_receipts=[]
        for rid in ['09344828-ca14-4d26-a64f-4f678bbf7070','fd02f51e-df34-4d65-9b3c-0a0cdf4a7202']:
            for fmt in ['markdown','html']:
                response=client.get('/api/market/reports/'+rid,params={'format':fmt});response.raise_for_status()
                assert 'AI draft withheld' in response.text
                assert 'pre-let over 4,300' not in response.text
                assert 'contracted to 21.6' not in response.text
                assert '5 unique URLs' not in response.text
                (OUT/f'{rid}.{fmt}').write_text(response.text,encoding='utf-8')
                report_receipts.append(dict(id=rid,format=fmt,status=response.status_code,withheld=True))
        dump('real-report-http.json',report_receipts)
        response=client.get('/api/market/overview');response.raise_for_status();dump('overview.json',response.json())
    facts=[]
    for quarter in ['Q1','Q2']:
        for metric in ['RENT','VACANCY','TAKEUP']:
            fact=store.get('facts',f'BNP-2026{quarter}-{metric}')
            assert fact is not None
            doc=store.get('documents',fact['document_id'])
            path=Path(doc['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest==doc['sha256']
            with fitz.open(path) as pdf:
                page=fact['evidence']['page'];page_text=pdf[page-1].get_text()
            quote=fact['evidence']['quote']
            found=' '.join(quote.split()) in ' '.join(page_text.split())
            assert found, (fact['id'],'quote not in PDF page')
            assert fact['human_review_status']!='approved'
            facts.append(dict(fact=fact,document=doc,actual_original_sha256=digest,quote_found_on_page=found,page_text=page_text))
    dump('six-core-facts-local-verification.json',facts)
    inventory=source_inventory(store)
    active=[f for f in store.all('facts') if f.get('status')!='superseded']
    approved=[f['id'] for f in active if f.get('human_review_status')=='approved']
    dump('comparison-eligibility.json',dict(active_fact_count=len(active),human_approved_fact_ids=approved,
        fully_eligible_pairs=0 if not approved else None,
        conclusion='No fully eligible real comparison while all facts remain pending human review.',inventory=inventory))
    changes=[]
    before=json.loads((OUT/'before-records.json').read_text(encoding='utf-8'))
    for table,rows in before.items():
        for row in rows:
            if store.get(table,row['id'])!=row:changes.append(dict(table=table,id=row['id']))
    original_errors=[]
    for doc in store.all('documents'):
        path=Path(doc['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=doc['sha256']:
            original_errors.append(doc['id'])
    frozen=json.loads((DATA/'evidence/protected-baseline.json').read_text(encoding='utf-8-sig'))
    protected_errors=[p for p,h in frozen.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    integrity=dict(original_record_counts={k:len(v) for k,v in before.items()},modified_original_records=changes,
        document_hashes_checked=len(store.all('documents')),document_hash_errors=original_errors,
        protected_files_checked=len(frozen),protected_file_errors=protected_errors)
    dump('integrity.json',integrity)
    assert not changes and not original_errors and not protected_errors
    print(json.dumps(dict(status='PASS',new_model_requests=0,inventory=inventory,integrity=integrity)))


if __name__=='__main__':main()
