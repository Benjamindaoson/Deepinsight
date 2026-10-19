"""Semantic contracts use isolated originals; fixtures are not live-market proof."""
import asyncio
import json
from london_product.store import Store
from london_product.sources import catalog, parse_content
from london_product.service import MarketService


def document(store, source, text):
    data=text.encode()
    return store.snapshot(source,source['url'],data,'text/plain',parse_content(data,'text/plain'))


def test_registry_covers_20_with_executable_sources():
    from london_product.indicators import definitions
    rows=definitions(); ids={s['id'] for s in catalog()}
    assert [m['id'] for m in rows]==[f'M{i:02}' for i in range(1,21)]
    assert all(m['source_ids'] and set(m['source_ids'])<=ids for m in rows)


def test_grade_a_not_prime_or_share_and_rent_annual_gate(tmp_path):
    from london_product.indicator_ingestion import project_document
    from london_product.indicators import coverage
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='savills-html')
    store.put('sources',s['id'],s)
    d=document(store,s,'Q2 2026. City average Grade A rent was £76.21 per sq ft. Prime City rents £116.73 per sq ft. Grade A share was 94%.')
    project_document(store,d,s); project_document(store,d,s)
    rows=store.all('facts'); grade=[f for f in rows if f.get('grade')=='Grade A']
    assert len(grade)==1 and grade[0]['value']=='76.21'
    assert grade[0]['normalized_value'] is None
    assert grade[0]['human_review_status']=='pending_review'
    assert grade[0]['evidence']['quote'] in d['segments'][0]['text']
    assert 'RENT_ANNUAL_BASIS_UNRESOLVED' in MarketService(store).review_eligibility(grade[0])['blockers']
    assert next(m for m in coverage(store)['metrics'] if m['id']=='M02')['fact_ids']==[grade[0]['id']]


def test_jll_area_prelet_under_offer_and_geography_are_separate(tmp_path):
    from london_product.indicator_ingestion import project_document
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='jll')
    text=('Central London\nOffice | Q2 2026\nTake-up reached 2.6 million sq.ft. in Q2 2026. '
          'Supply contracted for a third consecutive quarter to 21.6 million sq.ft., with the vacancy rate at 8.6%. '
          'Space under construction fell to 14.4 million sq.ft. '
          '80% of delivered space pre-let or under offer. Demand for best-in-class offices remains strong.')
    d=document(store,s,text);project_document(store,d,s)
    rows=store.all('facts')
    assert any(f['metric']=='availability' and f['normalized_value']=='21600000.0' for f in rows)
    assert any(f['metric']=='supply' and f['value']=='14.4' for f in rows)
    assert not any(f['metric'] in ['prelet','prelet_share'] and f['value']=='80' for f in rows)
    assert all(f['geography']=='Central London' for f in rows)
    assert any('flight_to_quality' in e.get('indicator_keys',[]) for e in store.all('events'))


def test_coverage_does_not_invent_canary_or_grade_a(tmp_path):
    from london_product.indicators import coverage
    store=Store(tmp_path)
    store.put('facts','f',dict(metric='rent',grade='Prime',geography='Canary Wharf & Docklands',value='58.5',unit='GBP/sqft',period='2026Q2',status='pending_review'))
    rows={m['id']:m for m in coverage(store)['metrics']}
    assert rows['M02']['fact_ids']==[]
    assert rows['M12']['exact_geography_fact_ids']==[]
    assert 'Canary Wharf & Docklands' in rows['M12']['source_geographies']


def test_macro_history_preserves_real_json_quote_and_revision(tmp_path):
    from london_product.indicator_ingestion import project_macro
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='ons')
    payload=dict(description=dict(cdid='L55O',unit='%',title='CPIH annual rate',releaseDate='2026-10-15'),months=[dict(date='2026 JUL',value='3.1'),dict(date='2026 AUG',value='3.0')])
    data=json.dumps(payload).encode(); d=store.snapshot(s,s['url'],data,'application/json',parse_content(data,'application/json'))
    project_macro(store,d,s,data);project_macro(store,d,s,data)
    assert len(store.all('facts'))==2
    for f in store.all('facts'):
        assert f['evidence']['quote'] in next(x['text'] for x in d['segments'] if x['locator']==f['evidence']['locator'])
    payload['months'][0]['value']='3.2'; data=json.dumps(payload).encode()
    d2=store.snapshot(s,s['url'],data,'application/json',parse_content(data,'application/json'))
    project_macro(store,d2,s,data)
    active=[f for f in store.all('facts') if f.get('status')!='superseded']
    assert len(active)==2 and any(f['value']=='3.2' for f in active)


def test_refresh_reprojects_304_original_without_duplicate(monkeypatch,tmp_path):
    from london_product import sources
    store=Store(tmp_path);service=MarketService(store)
    s=next(s for s in catalog() if s['id']=='jll');store.put('sources',s['id'],s)
    d=document(store,s,'Central London\nOffice | Q2 2026\nTake-up reached 2.6 million sq.ft. in Q2 2026.')
    async def fetch(*a,**kw):return dict(status_code=304,content=b'',media='text/plain',url=s['url'])
    monkeypatch.setattr(sources,'fetch_source',fetch)
    asyncio.run(service.refresh(dict(source_id='jll')));asyncio.run(service.refresh(dict(source_id='jll')))
    assert len(store.all('facts'))==1


def test_named_grade_query_excludes_prime_and_hybrid_returns_source(tmp_path):
    from london_product.indicator_ingestion import project_document
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='savills-html')
    d=document(store,s,'Q2 2026. City average Grade A rent was £76.21 per sq ft. Prime City rents £116.73 per sq ft. London office occupiers use hybrid working.')
    project_document(store,d,s);service=MarketService(store)
    answer,_=service.saved_answer('City Grade A rents')
    assert '76.21' in answer and '116.73' not in answer
    answer,_=service.saved_answer('What evidence exists for hybrid working?')
    assert 'savills.com' in answer and 'hybrid' in answer


def test_html_publication_is_source_metadata_not_collection_date():
    from london_product.sources import document_metadata
    data=b'<script type="application/ld+json">{"datePublished":"2023-02-13T00:00:00.000Z"}</script><main>History</main>'
    assert document_metadata(data,'text/html')['published_at']=='2023-02-13T00:00:00.000Z'
    assert document_metadata(b'<main>History</main>','text/html')=={}


def test_multi_region_overview_does_not_assign_city_vacancy_to_london(tmp_path):
    from london_product.indicator_ingestion import project_document
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='bnp')
    d=document(store,s,'Q2 2026 Central London office market. Market conditions in the City strengthen, with overall vacancy reducing to 9.4%.')
    project_document(store,d,s)
    assert not store.all('facts')


def test_gva_missing_source_unit_is_not_asserted_percent(tmp_path):
    from london_product.indicator_ingestion import project_macro
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='ons-gva')
    data=json.dumps(dict(description=dict(cdid='ECYX',unit='',title='Gross Value Added - Monthly (period on period growth) :CVM SA'),months=[dict(date='2026 AUG',value='0.1')])).encode()
    d=store.snapshot(s,s['url'],data,'application/json',parse_content(data,'application/json'))
    project_macro(store,d,s,data)
    assert store.all('facts')[0]['unit']=='source_unit_not_stated'


def test_report_preleased_share_does_not_generate_prelet_area(tmp_path):
    from london_product.indicator_ingestion import project_document
    store=Store(tmp_path);s=next(s for s in catalog() if s['id']=='jll')
    d=document(store,s,'Central London\nOffice | Q2 2026\nUnder construction\n14.4 million sq.ft.\nU/C preleased\n35%')
    project_document(store,d,s)
    shares=[f for f in store.all('facts') if f['metric']=='prelet_share']
    assert len(shares)==1 and shares[0]['value']=='35'
    assert not any(f['metric']=='prelet' for f in store.all('facts'))
