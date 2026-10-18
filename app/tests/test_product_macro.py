from pathlib import Path
from london_product.store import Store
from london_product.service import MarketService
from london_product.seed import seed_records


def test_real_saved_employment_period_and_duplicate_materialization(tmp_path):
    root=Path(__file__).resolve().parents[2]
    seed=seed_records(root);source=next(s for s in seed['sources'] if s['id']=='ons-employment')
    doc=next(d for d in seed['documents'] if d['source_id']=='ons-employment')
    fact=next(f for f in seed['facts'] if f.get('metric')=='employment')
    service=MarketService(Store(tmp_path))
    service.store.put('documents','doc',doc);service.store.put('facts',fact['id'],fact)
    service.macro_from_document(doc,source,Path(doc['path']).read_bytes())
    assert len(service.store.all('facts'))==1
    assert fact['period']=='2026 MAY-JUL' and fact['basis']=='rolling_three_month_average'
