"""Synthetic originals test monitoring provenance and withdrawal, not market facts."""
from pathlib import Path
import pytest
from test_chat_report import svc, observation

def pair(svc):
    observation(svc,'old',period='2026Q1',value='7')
    observation(svc,'new',period='2026Q2',value='9')

def test_approval_without_an_original_cannot_create_comparison_or_alert(svc):
    pair(svc)
    svc.store.update('facts','new',dict(document_id='MISSING-DOCUMENT'))
    result=svc.compare('old','new')
    assert result['status']=='not_comparable'
    assert result['absolute_change'] is None
    assert 'EVIDENCE_NOT_VERIFIED' in result['reasons']
    assert svc.monitor_changes()['alerts']==0

@pytest.mark.parametrize('change', ['superseded','regroup','tampered','pending_review'])
def test_previously_active_signal_is_retracted_when_input_ceases_to_qualify(svc,change):
    pair(svc)
    event_id=svc.monitor_changes()['event_ids'][0]
    if change=='superseded':svc.store.update('facts','old',dict(status='superseded'))
    if change=='regroup':svc.store.update('facts','old',dict(definition='different publisher definition'))
    if change=='pending_review':svc.store.update('facts','old',dict(human_review_status='pending_review'))
    if change=='tampered':
        d=svc.store.get('documents',svc.store.get('facts','old')['document_id'])
        Path(d['path']).write_bytes(b'tampered synthetic original')
    svc.invalidate()
    result=svc.monitor_changes()
    assert result['alerts']==0
    event=svc.store.get('events',event_id)
    assert event['status']=='superseded' and event['signal_status']=='retracted'
