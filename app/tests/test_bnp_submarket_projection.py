import pytest
from london_product.indicator_ingestion import project_document
from london_product.store import Store


def test_city_narrative_projection_preserves_raw_rent_and_flow(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text=('LEASING BY SUBMARKET: THE CITY Q2 2026\n'
          'Leasing activity across the City strengthened during Q2 2026, with take-\n'
          'up reaching approximately 1.1 million sq ft, representing a 15.2% increase. '
          'Available office space reducing to 8.9 million sq ft. '
          'Overall vacancy has continued to improve, falling to 9.4% during Q2 2026. '
          'Prime rents increased to £95.00 psf during Q2 2026. '
          'Premium rents remained at £150.00 psf.')
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=6,locator='pdf:page:6')])
    project_document(store,doc,source)
    rows={f['metric']:f for f in store.all('facts')}
    assert rows['takeup']['value']=='1.1'
    assert rows['availability']['value']=='8.9'
    assert rows['vacancy']['value']=='9.4'
    assert rows['rent']['value']=='95.00'
    assert rows['rent']['normalized_value'] is None
    assert 'supply' not in rows
    for row in rows.values():
        assert row['human_review_status']=='pending_review'
        assert row['evidence']['quote'] in text
        assert row['geography']=='City'


def test_canary_headline_conflict_retains_both_disclosures(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text=('LEASING BY SUBMARKET: CANARY WHARF & DOCKLANDS Q2 2026 '
          'take-up reaching approximately 166,000 sq ft. '
          '167k sq ft Q2 CANARY WHARF & DOCKLANDS TAKE-UP')
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=9,locator='pdf:page:9')])
    project_document(store,doc,source)
    rows=[f for f in store.all('facts') if f['metric']=='takeup']
    assert {r['value'] for r in rows}=={'166000','167000'}
    assert all(r['geography']=='Canary Wharf & Docklands' for r in rows)
    assert all(r['human_review_status']=='pending_review' for r in rows)


def test_explicit_rent_denominator_is_retained_without_human_approval(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text='LEASING BY SUBMARKET: THE CITY Q2 2026 Prime rents increased to £95.00 psf per annum.'
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=6,locator='pdf:page:6')])
    project_document(store,doc,source)
    row=next(f for f in store.all('facts') if f['metric']=='rent')
    assert 'per annum' in row['evidence']['quote']
    assert row['annualization']=='explicit'
    assert row['normalized_unit']=='GBP/sqft/year'
    assert row['human_review_status']=='pending_review'


def test_q1_relative_vacancy_clause_is_projected_with_same_series(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text=('LEASING BY SUBMARKET: WEST END Q1 2026 '
          'Constrained supply contributed to a further fall in vacancy, which reduced to 6.8%, '
          'below the five-year average of 7.5%.')
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/q1.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=5,locator='pdf:page:5')])
    project_document(store,doc,source)
    row=next(f for f in store.all('facts') if f['metric']=='vacancy')
    assert row['value']=='6.8' and row['period']=='2026Q1'
    assert row['series']=='Overall vacancy; submarket narrative'
    assert row['evidence']['quote']=='vacancy, which reduced to 6.8%'
    assert row['human_review_status']=='pending_review'


def test_jll_named_west_end_takeup_keeps_publisher_difference(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','jll',dict(id='jll',name='JLL',allow_llm=True))
    text=('Central London Office | Q2 2026 The West End was most active for the first time since Q3 2021 '
          'at 1.2 million sq.ft., followed by the City.')
    doc=store.snapshot(source,'https://www.jll.com/q2.pdf',text.encode(),'text/plain',
                       [dict(text=text,page=1,locator='pdf:page:1')])
    project_document(store,doc,source)
    row=next(f for f in store.all('facts') if f['metric']=='takeup' and f['geography']=='West End')
    assert row['value']=='1.2' and row['unit']=='million sq ft'
    assert row['period']=='2026Q2' and row['human_review_status']=='pending_review'
    assert 'West End' in row['evidence']['quote']


def test_west_end_availability_keeps_stock_separate_from_pipeline(tmp_path):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text=('LEASING BY SUBMARKET: WEST END Q2 2026 Office supply across the West End remained broadly stable during Q2, '
          'increasing marginally by 0.4% quarter-on-quarter to 6.2 million sq ft.')
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=5,locator='pdf:page:5')])
    project_document(store,doc,source)
    rows=[f for f in store.all('facts') if f['metric']=='availability']
    assert rows and rows[0]['value']=='6.2'
    assert not [f for f in store.all('facts') if f['metric']=='supply']


@pytest.mark.parametrize('suffix',['particularly for refurbished space','partially refurbished','per annually adjusted terms','p.a.rticular terms'])
def test_rent_word_prefix_cannot_become_annual_evidence(tmp_path,suffix):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text='LEASING BY SUBMARKET: THE CITY Q2 2026 Prime rents increased to £95.00 psf '+suffix
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=6,locator='pdf:page:6')])
    project_document(store,doc,source)
    row=next(f for f in store.all('facts') if f['metric']=='rent')
    assert row['annualization']=='unknown'
    assert row['normalized_value'] is None


@pytest.mark.parametrize('suffix',['per annum','per year','pa','p.a.'])
def test_rent_complete_annual_token_is_retained(tmp_path,suffix):
    store=Store(tmp_path)
    source=store.put('sources','bnp',dict(id='bnp',name='BNP',allow_llm=True))
    text='LEASING BY SUBMARKET: THE CITY Q2 2026 Prime rents increased to £95.00 psf '+suffix
    doc=store.snapshot(source,'https://www.realestate.bnpparibas.co.uk/report.pdf',text.encode(),
                       'text/plain',[dict(text=text,page=6,locator='pdf:page:6')])
    project_document(store,doc,source)
    row=next(f for f in store.all('facts') if f['metric']=='rent')
    assert row['annualization']=='explicit'
    assert row['human_review_status']=='pending_review'
