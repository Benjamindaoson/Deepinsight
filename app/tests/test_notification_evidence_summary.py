"""Offline transport capture; real HTTP acceptance runs separately."""
from test_finding_verification import svc,observation
from london_product.chat_report import build_report,render_markdown


def test_large_report_notification_preserves_referenced_evidence(svc,monkeypatch):
    import apprise
    observation(svc,'old',period='2026Q1',value='6.8')
    observation(svc,'new',period='2026Q2',value='6.7')
    report=build_report(svc,'Analyse City vacancy Q2 2026 historical change')
    report['limitations']+=['Additional context: '+'数'*10000]
    svc.store.update('reports',report['report_id'],dict(artifact=report))
    svc.save_settings(dict(notifications_enabled=True))
    monkeypatch.setenv('LONDON_NOTIFICATION_URL','json://127.0.0.1:1')
    received=[]
    class Capture:
        def add(self,url):return True
        def notify(self,**kwargs):received.append(kwargs['body']);return True
    monkeypatch.setattr(apprise,'Apprise',Capture)
    result=svc.notify(report['report_id'])
    assert result['status']=='sent'
    body=received[0]
    assert len(body.encode('utf-8'))<=12000
    for part in ['https://example.org/old','https://example.org/new','2026Q1','2026Q2','6.8','6.7',report['report_id'],'SHA-256','page 1','summary']:
        assert part in body
    assert 'not the full report' in body


def test_markdown_calculations_use_actual_fact_scope_and_periods(svc):
    observation(svc,'old',period='2026Q1',value='6.8')
    observation(svc,'new',period='2026Q2',value='6.7')
    report=build_report(svc,'Analyse City vacancy Q2 2026 historical change')
    assert 'vacancy · City: 2026Q1 → 2026Q2 = -0.10 pp' in render_markdown(report)
