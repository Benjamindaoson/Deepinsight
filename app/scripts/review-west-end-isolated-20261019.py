"""Two individually reviewed original disclosures under explicit user delegation.

Not bulk approval, model self-approval, semantic approval or a formal DB change.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.service import MarketService

OUT=ROOT/'docs/delivery/real-e2e-20261019'
receipt_path=OUT/'DELEGATED_REVIEW_RECEIPT.json'
if receipt_path.exists():raise SystemExit('Review already recorded; preserve its audit trail.')
packet=json.loads((OUT/'REVIEW_PACKET.json').read_text(encoding='utf-8'))
assert len(packet['rows'])==2
store=Store(OUT/'runtime');service=MarketService(store);reviews=[]
try:
    for evidence in packet['rows']:
        row=store.get('facts',evidence['fact_id']);doc=store.get('documents',row['document_id'])
        assert row['source_id']=='bnp' and row['geography']=='West End' and row['metric']=='vacancy'
        assert (row['period'],row['value']) in [('2026Q1','6.8'),('2026Q2','6.7')]
        assert all(row.get(k)==evidence[k] for k in ['definition','method','series','basis','grade','period','value','unit'])
        assert hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()==evidence['document_sha256']==doc['sha256']
        assert any(row['evidence']['quote'] in seg['text'] and seg.get('page')==5 and 'WEST END' in seg['text'] for seg in doc['segments'])
        assert service.review_eligibility(row)['eligible']
        note=('User explicitly delegated handling of this two-record review packet on 2026-10-19. '
            'Codex individually checked source PDF page 5, West End heading, quarter, narrative/card, original SHA-256, '
            'value/unit and matching stock-rate metadata; independent read-only review agrees. '
            'Q2 lower chart has a misleading Prime Rent title; rely on explicit vacancy narrative and key figure card. '
            'Q2 precise publication date remains unknown. This is delegated source-evidence review in an isolated acceptance copy, '
            'not a claim that the user personally inspected the PDF, and not independent semantic/investment approval.')
        result=service.review_fact(row['id'],'approve','Codex - user-delegated evidence review',note)
        store.update('reviews',result['review']['id'],dict(review_type='user_delegated_source_evidence',
            authority='Direct user reply to scoped review request: 你自行处理',independent_semantic_approval=False))
        reviews.append(dict(fact_id=row['id'],prior_status=row['status'],prior_review_status=row.get('human_review_status'),
            review_id=result['review']['id'],new_status=result['fact']['status'],new_review_status=result['fact']['human_review_status'],
            document_sha256=doc['sha256'],period=row['period'],value=row['value']))
    receipt=dict(at=now(),scope='Only two named West End vacancy records in isolated acceptance copy',
        execution='User-delegated evidence review by Codex; not personal human PDF inspection',
        formal_database_writes=0,semantic_approval=False,reviews=reviews)
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))
finally:service.pool.shutdown(wait=True);store.engine.dispose()
