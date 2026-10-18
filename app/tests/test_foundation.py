"""Fault fixtures are explicitly synthetic, never market observations."""
import importlib.util
from decimal import Decimal
import pytest


def load(name):
    assert importlib.util.find_spec('london_data.' + name), f'Missing B1 {name} behavior'
    return __import__('london_data.' + name, fromlist=['*'])


def fact(**changes):
    data = dict(metric='rent', value='92.50', unit='GBP/sqft/year', source_id='bnp',
                series='office', geography='City', definition='prime', period='2026Q1',
                basis='quarter_end', grade='prime', method='research-v1', status='validated',
                currency='GBP', precision='0.01', evidence={'segment_id':'p3','quote':'Prime City rent £92.50 per sq ft per annum'},
                document_id='doc-old', attempt_id='a-old')
    data.update(changes)
    return data


def test_compare_rent_and_pp_and_zero():
    c=load('comparison')
    r=c.compare(fact(),fact(value='95',period='2026Q2',document_id='new'))
    assert r['status']=='comparable' and Decimal(r['absolute_change'])==Decimal('2.50')
    assert Decimal(r['relative_change_pct']).quantize(Decimal('.0001'))==Decimal('2.7027')
    r=c.compare(fact(metric='vacancy',value='8',unit='percent',currency=None),fact(metric='vacancy',value='9',unit='percent',currency=None,period='2026Q2'))
    assert r['absolute_change']=='1' and r['change_unit']=='pp'
    r=c.compare(fact(value='0'),fact(period='2026Q2'))
    assert r['relative_change_pct'] is None and 'ZERO_BASE' in r['warnings']


@pytest.mark.parametrize('field,value', [('source_id','other'),('geography','West End'),('definition','premium'),('method','other'),('basis','YTD'),('grade','Grade B'),('status','needs_review'),('currency','USD'),('series','other'),('unit','GBP/sqft/unknown')])
def test_incompatible_dimensions_fail_closed(field,value):
    c=load('comparison');r=c.compare(fact(),fact(**{field:value,'period':'2026Q2'}))
    assert r['status']=='not_comparable' and r['absolute_change'] is None
    assert r['reasons']


@pytest.mark.parametrize('period',['2026Q1','2025Q4','2026Q3','unknown'])
def test_quarter_direction_and_continuity(period):
    r=load('comparison').compare(fact(),fact(period=period))
    assert r['status']=='not_comparable'


def test_unit_conversion_and_unknown_rejected():
    c=load('comparison')
    r=c.compare(fact(metric='takeup',unit='sqft',currency=None,basis='quarter',value='100'),fact(metric='takeup',unit='sqm',currency=None,basis='quarter',value='10',period='2026Q2'))
    assert r['status']=='comparable' and Decimal(r['absolute_change'])==Decimal('7.639104167097')
    assert c.compare(fact(method=None),fact(period='2026Q2',method=None))['status']=='not_comparable'


def test_html_and_pdf_locations():
    d=load('documents')
    segments=d.parse_document(b'<html><script>ignore()</script><article><h1>Report</h1><p>Vacancy 8.4%</p></article></html>','text/html')
    assert any(s['text']=='Vacancy 8.4%' and s['segment_id'] for s in segments)
    assert not any('ignore()' in s['text'] for s in segments)
    import pymupdf
    doc=pymupdf.open();p=doc.new_page();p.insert_text((40,40),'Vacancy 8.4%')
    result=d.parse_document(doc.tobytes(),'application/pdf')
    assert result[0]['page']==1 and '8.4%' in result[0]['text']
    with pytest.raises(ValueError):d.parse_document(b'%PDF-corrupt','application/pdf')
    scanned=pymupdf.open();scanned.new_page()
    with pytest.raises(ValueError):d.parse_document(scanned.tobytes(),'application/pdf')


@pytest.mark.parametrize('url',['http://www.realestate.bnpparibas.co.uk/x','file:///C:/x','https://127.0.0.1/x','https://localhost/x','https://evil.example/x','https://www.realestate.bnpparibas.co.uk@127.0.0.1/x'])
def test_fetch_policy_blocks_unsafe_destinations(url):
    with pytest.raises(ValueError):load('documents').check_url(url,{'www.realestate.bnpparibas.co.uk'})


def test_validation_requires_exact_value_and_unit_and_location():
    v=load('validation')
    seg=[{'segment_id':'p3','page':3,'text':'Prime City rent £92.50 per sq ft per annum'}]
    assert v.validate(fact(),seg)['status']=='validated'
    assert v.validate(fact(value='95'),seg)['status']!='validated'
    assert v.validate(fact(evidence={'segment_id':'p9','quote':'rent 92.50'}),seg)['status']!='validated'
    assert v.validate(fact(unit='GBP/sqft/unknown'),seg)['status']!='validated'
    assert v.validate(fact(value=None),seg)['status']!='validated'


def test_storage_idempotence_atomicity_and_recovery(tmp_path):
    S=load('store').Repository;s=S(tmp_path/'test.db')
    doc=s.snapshot('bnp','https://example.org/a',b'actual fixture','text/html',None,[])
    assert s.snapshot('bnp','https://example.org/b',b'actual fixture','text/html',None,[])['id']==doc['id']
    a=s.attempt(doc['id'],'v1','run1')
    with pytest.raises(RuntimeError):s.persist(a,[fact(document_id=doc['id'])],fail_after_first=True)
    assert s.observations()==[]
    failed_id=a['id'];a=s.attempt(doc['id'],'v1','retry-run')
    s.persist(a,[fact(document_id=doc['id'])]);s.persist(a,[fact(document_id=doc['id'])])
    assert len(s.observations())==1
    assert s.get('attempts',failed_id)['status']=='failed'
    assert S(tmp_path/'test.db').observations()[0]['document_id']==doc['id']


def test_same_period_conflict_keeps_history(tmp_path):
    s=load('store').Repository(tmp_path/'x.db')
    d=s.snapshot('bnp','https://example.org/a',b'v1','text/html',None,[])
    a=s.attempt(d['id'],'v1','run1');s.persist(a,[fact(document_id=d['id'])])
    d2=s.snapshot('bnp','https://example.org/a',b'v2','text/html',None,[])
    a2=s.attempt(d2['id'],'v1','run2');s.persist(a2,[fact(document_id=d2['id'],value='95')])
    assert len(s.observations(include_all=True))==2
    assert all(x['status']=='needs_review' for x in s.observations(include_all=True))


def test_budget_stops_before_extra_provider_requests():
    B=load('extraction').Budget;b=B(max_requests=1)
    b.before(100,100);b.after(100,20)
    with pytest.raises(ValueError):b.before(100,100)
    with pytest.raises(ValueError):B().before(60001,1)
