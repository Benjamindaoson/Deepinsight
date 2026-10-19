"""Offline synthetic fixtures; no live source approvals or model calls."""
from test_finding_verification import svc,observation
import pytest


@pytest.mark.parametrize('change,alerts',[('0.49',0),('0.50',0),('0.51',1)])
def test_threshold_is_strictly_greater_than_configured_pp(svc,change,alerts):
    from decimal import Decimal
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value=str(Decimal('8')+Decimal(change)))
    assert svc.monitor_changes()['alerts']==alerts


def test_pending_duplicate_cannot_hide_an_approved_pair(svc):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value='9')
    new=svc.store.get('facts','new')
    svc.store.put('facts','pending-duplicate',dict(new,id='pending-duplicate',status='pending_review',human_review_status='pending_review'))
    result=svc.monitor_changes(detection_context='historical_replay')
    assert result['alerts']==1
    event=svc.store.get('events',result['event_ids'][0])
    assert event['old_id']=='old' and event['new_id']=='new'


def test_conflicting_approved_same_period_values_withhold_the_signal(svc):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value='9')
    observation(svc,'conflicting',period='2026Q2',value='10')
    result=svc.monitor_changes()
    assert result['alerts']==0
    assert not [e for e in svc.store.all('events') if e.get('kind')=='metric_change' and e.get('status')!='superseded']


def test_same_value_duplicate_keeps_existing_signal_identity(svc):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value='9')
    first=svc.monitor_changes()
    duplicate=dict(svc.store.get('facts','new'),id='a-duplicate')
    svc.store.put('facts','a-duplicate',duplicate)
    again=svc.monitor_changes()
    assert again['event_ids']==first['event_ids']


@pytest.mark.parametrize('value',['NaN','Infinity','not supplied','-1','101'])
def test_invalid_approved_values_do_not_crash_or_create_a_signal(svc,value):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'bad',period='2026Q2',value=value)
    result=svc.monitor_changes()
    assert result['alerts']==0
    assert any(d['status']=='invalid_observation' for d in result['decisions'])


@pytest.mark.parametrize('approved',[False,True])
def test_unrelated_pending_rent_normalization_failure_does_not_hide_valid_pair(svc,approved):
    observation(svc,'old',period='2026Q1',value='8')
    observation(svc,'new',period='2026Q2',value='9')
    observation(svc,'bad-rent',metric='rent',value='not supplied',unit='GBP/sqft/year',approved=approved)
    result=svc.monitor_changes()
    assert result['alerts']==1
    assert any(d['status']=='invalid_observation' and d.get('fact_ids')==['bad-rent'] for d in result['decisions'])
