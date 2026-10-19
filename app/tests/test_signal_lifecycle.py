from london_product.store import Store
from london_product.service import MarketService


def _facts(store):
    common = dict(source_id='sample', series='same-series', metric='vacancy',
                  geography='City', definition='vacant stock / stock',
                  basis='quarter_end', grade='all', method='same-method',
                  unit='percent', status='validated',human_review_status='approved')
    store.put('facts', 'old', dict(common,id='old',value='8.0',period='2026Q1'))
    store.put('facts', 'new', dict(common,id='new',value='8.8',period='2026Q2'))
    store.put('sources','sample',dict(id='sample',name='Synthetic fixture',allow_llm=True))
    for identity in ['old','new']:
        fact=store.get('facts',identity)
        quote=f"Synthetic fixture {fact['period']} vacancy {fact['value']} percent."
        doc=store.snapshot(dict(id='sample'),'https://example.org/synthetic/'+identity,quote.encode(),
            'text/plain',[dict(text=quote,page=1,locator='fixture:1')])
        store.update('facts',identity,dict(document_id=doc['id'],evidence=dict(quote=quote,page=1,locator='fixture:1')))


def test_signal_is_stable_and_retracted_when_review_is_removed(tmp_path):
    store = Store(tmp_path); _facts(store)
    service = MarketService(store)
    first = service.monitor_changes()
    assert first['alerts'] == 1
    current = [row for row in store.all('events') if row.get('kind') == 'metric_change']
    assert len(current) == 1
    signal_id = current[0]['signal_identity']
    assert current[0]['review_status'] == 'approved'
    assert service.monitor_changes()['alerts'] == 1
    assert len([row for row in store.all('events') if row.get('status') != 'superseded']) == 1

    store.update('facts', 'new', {'human_review_status':'pending_review'})
    assert service.monitor_changes()['alerts'] == 0
    retracted = store.get('events', current[0]['id'])
    assert retracted['status'] == 'superseded'
    assert retracted['signal_identity'] == signal_id
    assert retracted['superseded_reason'] == 'comparison_not_comparable'
