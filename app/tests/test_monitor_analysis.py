"""Synthetic market snapshots and model events; no paid/external requests."""
import json
from types import SimpleNamespace
import pytest
from test_finding_verification import svc,observation
from london_product.chat_report import ACTIVE_REPORT,build_report


def changes(svc):
    observation(svc,'old',period='2026Q1',value='7')
    observation(svc,'new',period='2026Q2',value='9')
    return svc.monitor_changes(detection_context='historical_replay')


def test_monitor_can_opt_in_to_existing_scoped_agent_once_before_notification(svc,monkeypatch):
    detected=changes(svc)
    svc.save_settings(dict(monitor_analysis_enabled=True,notifications_enabled=True))
    calls=[];notified=[]
    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))
        def run(self,prompt):
            calls.append(ACTIVE_REPORT.get())
            return SimpleNamespace(run_id='SYNTHETIC-agent',status='COMPLETED',content=json.dumps(dict(key_findings=[
                dict(text='City vacancy in 2026Q2 was 9 percent.',classification='inference',evidence_ids=['new'])])))
    svc.agent_factory=OfflineAgent
    monkeypatch.setattr(svc,'notify',lambda rid:notified.append(rid) or dict(id='SYNTHETIC-notification',status='sent'))
    first=svc.monitor_intelligence(detected,detection_context='historical_replay')
    assert len(calls)==1 and len(notified)==1 and calls==notified==[first[0]['report_id']]
    event=svc.store.get('events',detected['event_ids'][0])
    assert event['analysis_status']=='published' and event['analysis_id']
    assert svc.store.get('reports',event['report_id'])['artifact']['ai_analysis']['status']=='published'
    second=svc.monitor_intelligence(detected,detection_context='historical_replay')
    assert second[0]['deduplicated'] and len(calls)==1 and len(notified)==1
    assert ACTIVE_REPORT.get() is None


def test_failed_monitor_analysis_keeps_report_and_never_sends_or_retries(svc,monkeypatch):
    detected=changes(svc);svc.save_settings(dict(monitor_analysis_enabled=True,notifications_enabled=True))
    calls=[]
    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)),budget=SimpleNamespace(record=lambda:dict(requests=0)))
        def run(self,prompt):calls.append(prompt);raise RuntimeError('insufficient_user_quota PRIVATE')
    svc.agent_factory=OfflineAgent
    monkeypatch.setattr(svc,'notify',lambda _:pytest.fail('No notification on failed analysis'))
    result=svc.monitor_intelligence(detected)
    event=svc.store.get('events',detected['event_ids'][0])
    assert event['analysis_status']=='failed' and event['notification_status']=='analysis_not_publishable'
    assert event['report_id'] and svc.store.get('reports',event['report_id'])['artifact']['ai_analysis']['status']=='failed'
    svc.monitor_intelligence(detected)
    assert len(calls)==1 and ACTIVE_REPORT.get() is None
    job=svc.store.get('jobs',event['analysis_id'])
    assert job['error_code']=='PROVIDER_QUOTA_EXHAUSTED' and 'PRIVATE' not in job.get('error','')


def test_scoped_analysis_refuses_pending_only_evidence_without_model(svc):
    observation(svc,'pending',approved=False)
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    svc.agent_factory=lambda:pytest.fail('Do not spend model requests without eligible observations')
    result=svc.report_analysis(report_id=report['report_id'])
    assert result['analysis_status']=='blocked' and result['error_code']=='NO_VERIFIED_EVIDENCE'
    assert result['metrics']['requests']==0


@pytest.mark.parametrize('inside_event_loop', [False, True])
def test_scoped_analysis_uses_async_native_entry_and_preserves_report_context(svc, inside_event_loop):
    import asyncio
    observation(svc,'async-evidence')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    calls=[]
    class AsyncAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))
        def run(self,*args):raise ValueError('Cannot use an async hook with run(). Use arun() instead.')
        async def arun(self,prompt):
            await asyncio.sleep(0)
            calls.append(ACTIVE_REPORT.get())
            return SimpleNamespace(run_id='SYNTHETIC-async',status='COMPLETED',content=json.dumps(dict(key_findings=[
                dict(text='City vacancy in 2026Q2 was 8 percent.',classification='inference',evidence_ids=['async-evidence'])])))
    svc.agent_factory=AsyncAgent
    async def invoke():return svc.report_analysis(report_id=report['report_id'])
    result=asyncio.run(invoke()) if inside_event_loop else svc.report_analysis(report_id=report['report_id'])
    assert result['analysis_status']=='published'
    assert calls==[report['report_id']] and ACTIVE_REPORT.get() is None


def test_recovery_marks_claimed_monitor_analysis_interrupted_without_replay(svc):
    detected=changes(svc)
    report=build_report(svc,'Analyse City vacancy change Q2 2026')
    job=svc.store.put('jobs','SYNTHETIC-crashed',dict(kind='analysis',status='running',report_id=report['report_id']))
    event_id=detected['event_ids'][0]
    svc.store.update('events',event_id,dict(report_id=report['report_id'],analysis_status='running'))
    svc.recover_jobs()
    event=svc.store.get('events',event_id)
    assert event['analysis_status']=='interrupted' and event['analysis_id']==job['id']
    assert svc.monitor_intelligence(detected)[0]['deduplicated']


def published_report(svc):
    observation(svc,'revocable')
    report=build_report(svc,'Analyse City vacancy Q2 2026')
    class OfflineAgent:
        model=SimpleNamespace(budget_for=lambda _:SimpleNamespace(record=lambda:dict(requests=0)))
        def run(self,prompt):
            return SimpleNamespace(run_id='SYNTHETIC-revocation',status='COMPLETED',content=json.dumps(dict(key_findings=[
                dict(text='City vacancy in 2026Q2 was 8 percent.',classification='inference',evidence_ids=['revocable'])])))
    svc.agent_factory=OfflineAgent
    assert svc.report_analysis(report_id=report['report_id'])['analysis_status']=='published'
    svc.store.update('facts','revocable',dict(status='rejected',human_review_status='rejected'))
    svc.agent_factory=lambda:pytest.fail('Revocation must not trigger another model call')
    return report['report_id']


def test_scoped_cache_revalidates_publication_but_preserves_execution_receipt(svc):
    rid=published_report(svc)
    result=svc.report_analysis(report_id=rid)
    assert result['cached'] and result['analysis_status']=='withheld'
    assert result['execution_receipt']['analysis_status']=='published'
    assert result['error_code']=='EVIDENCE_CHANGED'
    assert svc.store.get('jobs','scoped-analysis:'+rid)['result']['analysis_status']=='published'


def test_notification_refuses_revoked_structured_report_before_transport(svc,monkeypatch):
    import apprise
    rid=published_report(svc)
    svc.save_settings(dict(notifications_enabled=True))
    monkeypatch.setenv('LONDON_NOTIFICATION_URL','json://127.0.0.1:1')
    monkeypatch.setattr(apprise,'Apprise',lambda:pytest.fail('Withheld evidence cannot reach transport'))
    result=svc.notify(rid)
    assert result['status']=='publication_withheld' and result['attempts']==0
    assert result['error']=='EVIDENCE_CHANGED'
