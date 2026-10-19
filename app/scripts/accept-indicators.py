"""Real free acquisition acceptance; requires an existing isolated baseline copy."""
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store
from london_product.service import MarketService
from london_product.sources import catalog
from london_product.indicator_ingestion import VERSION
from london_product.indicators import coverage
out=Path(sys.argv[1]).resolve()
if not out.is_relative_to(ROOT/'docs/delivery') or not (out/'isolated/market.sqlite3').is_file():
    raise SystemExit('Existing isolated delivery copy required')
os.environ['LONDON_TAVILY_ENABLED']='0'
os.environ.pop('LONDON_NOTIFICATION_URL',None)
store=Store(out/'isolated');service=MarketService(store)
# Only this run's obsolete provisional adapter records are retired. Seed/user
# records are not edited; original failed acceptance evidence is retained.
retired=[]
for fact in store.all('facts'):
    if fact.get('extraction_version')=='indicator-projection-v1' and fact.get('status')!='superseded':
        store.update('facts',fact['id'],dict(status='superseded',reason='Provisional v1 projection replaced after geographic/unit regression'))
        retired.append(fact['id'])

async def main():
    semaphore=asyncio.Semaphore(2)
    async def one(s):
        async with semaphore:
            prior=store.get('sources',s['id'])
            if prior:store.update('sources',prior['id'],dict({k:v for k,v in s.items() if k!='id'},etag=None,last_modified=None))
            else:store.put('sources',s['id'],s)
            stamp=datetime.now(timezone.utc).isoformat()
            if not s.get('enabled'):return dict(source_id=s['id'],at=stamp,status='blocked',reason=s.get('health'))
            result=await service.refresh(dict(source_id=s['id']))
            return dict(source_id=s['id'],at=stamp,**result)
    results=await asyncio.gather(*(one(s) for s in catalog() if s['id'] not in ['planning','knightfrank']))
    facts=[f for f in store.all('facts') if f.get('extraction_version')==VERSION and f.get('status')!='superseded']
    checks=[]
    for f in facts:
        doc=store.get('documents',f['document_id']);ev=f['evidence']
        valid_hash=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()==doc['sha256']
        segment=next((s for s in doc['segments'] if s.get('locator')==ev['locator']),{})
        quote_valid=bool(ev['quote']) and ev['quote'] in segment.get('text','')
        checks.append(dict(fact_id=f['id'],source_id=f['source_id'],metric=f['metric'],geography=f['geography'],period=f['period'],value=f['value'],unit=f['unit'],document_id=doc['id'],sha256=doc['sha256'],original_hash_valid=valid_hash,quote_valid=quote_valid,quote=ev['quote'],locator=ev['locator'],human_review_status=f['human_review_status']))
    before={k:len(store.all(k)) for k in ['facts','events']}
    # Reproject only the new exact originals, without another network call.
    from london_product.indicator_ingestion import project_document,project_macro
    current_sources={s['id']:s for s in store.all('sources')}
    refreshed={r['document_id'] for result in results for r in result.get('sources',[]) if r.get('document_id')}
    refreshed|={a['document_id'] for result in results for r in result.get('sources',[]) for a in r.get('articles',[]) if a.get('document_id')}
    for did in refreshed:
        d=store.get('documents',did);s=current_sources[d['source_id']]
        project_document(store,d,s)
        if s['id'] in ['boe','ons','ons-employment','ons-gva']:project_macro(store,d,s,Path(d['path']).read_bytes())
    after={k:len(store.all(k)) for k in before}
    report=service.report('weekly',key='indicator-acceptance-'+datetime.now().strftime('%H%M%S'))
    queries={q:service.saved_answer(q)[0] for q in [
        'What is the recent trend in prime office rents in London West End?',
        'Compare City and Canary Wharf rents vacancy and leasing activity',
        'What are the latest notable changes in the Canary Wharf office market?',
        'What evidence exists for hybrid working?', 'City Grade A rents']}
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),version=VERSION,paid_model_calls=0,paid_search_calls=0,external_notifications=0,
                 sources=results,retired_provisional_records=retired,refreshed_document_ids=sorted(refreshed),
                 provenance_checks=checks,all_provenance_pass=all(c['original_hash_valid'] and c['quote_valid'] for c in checks),
                 idempotency=dict(before=before,after=after,passed=before==after),coverage=coverage(store),queries=queries,
                 active_adapter_facts=len(facts),by_metric=dict(Counter(f['metric'] for f in facts)),report_id=report['id'])
    (out/'indicator-acceptance.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:receipt[k] for k in ['at','version','active_adapter_facts','by_metric','all_provenance_pass','idempotency','report_id']},indent=2))
    if not receipt['all_provenance_pass'] or before!=after:raise SystemExit(1)
asyncio.run(main())
