"""Catch unsupported annualization, legacy approval bypass and false trend release."""
import pytest
from london_product.normalization import derive
from london_product.service import MarketService
from london_product.store import Store
from london_product.directional import assess
from london_product.analysis_guard import review_analysis
from london_product.qa_context import verified


@pytest.fixture
def service(tmp_path):
    return MarketService(Store(tmp_path))


def fact(identity='q1', **patch):
    row = dict(id=identity, metric='vacancy', value='8', normalized_value='8', unit='percent',
        normalized_unit='percent', geography='City', normalized_period='2026Q1', period='2026Q1',
        source_id='publisher-a', series='overall', definition='overall office vacancy', basis='stock',
        method='publisher sample', grade='all', currency=None, status='pending_review',
        human_review_status='pending_review', document_id='doc', evidence={'quote':'Vacancy 8 percent.'})
    return dict(row, **patch)


@pytest.mark.parametrize('unit', ['GBP/sqft', 'GBP/sqft/year'])
def test_annual_rent_requires_source_wording_even_if_model_unit_says_year(unit):
    result = derive(fact(metric='rent', value='95', unit=unit, evidence={'quote':'Prime rents £95 per sq ft.'}))
    assert result['annualization'] == 'unknown'
    assert result['normalized_value'] is None


def test_explicit_source_annual_rent_is_still_available():
    result = derive(fact(metric='rent', value='95', unit='GBP/sqft', evidence={'quote':'Prime rents £95 per sq ft per annum.'}))
    assert result['annualization'] == 'explicit'
    assert result['normalized_value'] == '95'
    assert result['normalized_unit'] == 'GBP/sqft/year'


@pytest.mark.parametrize('quote,expected', [('Prime rent £95/sq.ft./annum.','explicit'),('Spa office rent £95 per sq ft.','unknown')])
def test_annual_source_wording_is_a_complete_time_denominator(quote,expected):
    assert derive(fact(metric='rent',value='95',unit='GBP/sqft',evidence={'quote':quote}))['annualization']==expected


def test_unrecognized_numeric_paraphrase_is_not_semantically_approved(service):
    raw='Canary Wharf vacancy doubled to 25 percent in 2026Q3.'
    result=review_analysis(raw,service.store)
    assert result['publication_review']['status']=='withheld'
    assert raw not in result['answer']


def test_generic_note_cannot_approve_legacy_convention_rent(service):
    service.store.put('documents', 'doc', {'id':'doc'})
    row=fact(metric='rent', value='95', unit='GBP/sqft', annualization='industry_convention')
    service.store.put('facts', row['id'], row)
    with pytest.raises(ValueError, match='RENT_ANNUAL_BASIS_UNRESOLVED'):
        service.review_fact(row['id'], 'approve', 'reviewer', 'confirmed convention')


def test_legacy_approved_rent_is_not_verified_and_read_does_not_rewrite_db(service):
    row=fact(metric='rent', value='95', unit='GBP/sqft', annualization='industry_convention',
             normalized_unit='GBP/sqft/year', status='validated', human_review_status='approved')
    service.store.put('facts', row['id'], row)
    assert verified(row) is False
    shown=service.facts()['items'][0]
    assert shown['normalized_value'] is None
    assert shown['status'] != 'validated'
    assert shown['human_review_status'] != 'approved'
    assert service.store.get('facts',row['id'])['status']=='validated'


@pytest.mark.parametrize('changed', ['source_id','series','method','basis','grade','currency'])
def test_directional_never_merges_incompatible_series(service, changed):
    old=fact()
    new=fact('q2', value='9', normalized_value='9', period='2026Q2', normalized_period='2026Q2')
    new[changed]='different'
    for row in [old,new]:service.store.put('facts',row['id'],row)
    assert assess(service.store)['series'] == []


def test_unrelated_series_cannot_release_wrong_geo_period_magnitude(service):
    for row in [fact(),fact('q2', value='9', normalized_value='9', period='2026Q2', normalized_period='2026Q2')]:
        service.store.put('facts',row['id'],row)
    raw='Canary Wharf office vacancy rose 25 percentage points in Q3 2026.'
    answer=review_analysis(raw,service.store)
    assert answer['publication_review']['status']=='withheld'
    assert raw not in answer['answer']
    assert answer['raw_answer']==raw


def test_saved_comparison_returns_all_requested_metrics_and_skips_rejected(service):
    for row in [fact(),fact('rent',metric='rent',unit='GBP/sqft'),fact('takeup',metric='takeup',unit='sqft'),
                fact('bad',status='rejected',human_review_status='rejected')]:
        service.store.put('facts',row['id'],row)
    answer,_=service.saved_answer('Compare City rents, vacancy and leasing activity in 2026Q1')
    assert ' · rent · ' in answer
    assert ' · vacancy · ' in answer
    assert ' · takeup · ' in answer
    assert '[rejected]' not in answer


def test_legacy_approved_annual_rent_cannot_bypass_comparator(service):
    base=dict(metric='rent', unit='GBP/sqft', normalized_unit='GBP/sqft/year', value='95',
              normalized_value='95', normalization_version='old', annualization='industry_convention',
              currency='GBP', status='validated', human_review_status='approved')
    for row in [fact(**base),fact('q2',**dict(base,value='100',normalized_value='100',period='2026Q2',normalized_period='2026Q2'))]:
        service.store.put('facts',row['id'],row)
    result=service.compare('q1','q2')
    assert result['status']=='not_comparable'
    assert result['absolute_change'] is None


def test_same_period_conflicting_values_do_not_choose_a_winner(service):
    for row in [fact(),fact('conflict',value='7',normalized_value='7'),fact('q2',value='9',normalized_value='9',period='2026Q2',normalized_period='2026Q2')]:
        service.store.put('facts',row['id'],row)
    assert assess(service.store)['series']==[]


def test_unknown_method_cannot_establish_directional_comparability(service):
    for row in [fact(method='unknown'),fact('q2',method='unknown',value='9',normalized_value='9',period='2026Q2',normalized_period='2026Q2')]:
        service.store.put('facts',row['id'],row)
    assert assess(service.store)['series']==[]


def test_daily_news_window_accepts_date_only_and_excludes_old_events(service):
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).date().isoformat()
    for identity,published in [('today',stamp),('old','2000-01-01'),('undated',None)]:
        service.store.put('events',identity,dict(id=identity,title=identity,kind='news',published_at=published,geography='City'))
    report=service.report('daily')
    assert report['recent_event_ids']==['today']


def test_isolated_origin_can_be_configured_without_opening_arbitrary_origins(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False,frontend_port=3102)
    with TestClient(app) as client:
        allowed=client.post('/api/market/ask',json={'message':'City rents','mode':'saved'},headers={'Origin':'http://127.0.0.1:3102'})
        denied=client.post('/api/market/ask',json={'message':'City rents','mode':'saved'},headers={'Origin':'https://untrusted.example'})
        assert allowed.status_code==200
        assert 'Which rent measure' in allowed.text
        assert denied.status_code==403


def test_scoped_report_preserves_background_periods_and_window(service):
    for row in [fact(),fact('west',geography='West End')]:service.store.put('facts',row['id'],row)
    report=service.report('daily',geography='City')
    assert report['fact_ids']==['q1']
    assert report['geography']=='City'
    assert report['window_days']==1
    assert '2026Q1' in report['markdown']
    assert 'historical background' in report['markdown']
    with pytest.raises(ValueError,match='another scope'):
        service.report('weekly',key='same',geography='City')
        service.report('weekly',key='same',geography='West End')
