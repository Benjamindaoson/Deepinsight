"""Offline scheduler regressions: simulated source failures are not live evidence."""
from fastapi.testclient import TestClient
from agno.db.sqlite import SqliteDb
from agno.scheduler import ScheduleManager
from london_product.runtime import create_app
import asyncio


def test_native_registration_is_idempotent_and_can_disable(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    service.schedule_manager=ScheduleManager(SqliteDb(db_file=str(tmp_path/'scheduler.sqlite3')))
    service.sync_schedules()
    first={s.name:s.id for s in service.schedule_manager.list()}
    service.sync_schedules()
    assert {s.name:s.id for s in service.schedule_manager.list()}==first
    assert len(first)==4
    service.save_settings({'monitoring_enabled':False})
    assert all(not s.enabled for s in service.schedule_manager.list())
    service.pool.shutdown()


def test_scheduled_failure_http_status_and_replay(tmp_path,monkeypatch):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    calls=[]
    def failure(job):
        calls.append(job['id'])
        service.store.update('jobs',job['id'],dict(status='failed',error='All selected sources failed'))
    monkeypatch.setattr(service,'_run_job',failure)
    with TestClient(app) as client:
        first=client.post('/api/market/scheduled/news',headers={'Idempotency-Key':'offline-failure'})
        second=client.post('/api/market/scheduled/news',headers={'Idempotency-Key':'offline-failure'})
        assert first.status_code==second.status_code==503
        assert first.json()['id']==second.json()['id'] and second.json()['deduplicated']
        assert len(calls)==1
        # No key means an explicit new occurrence, including a native retry.
        assert client.post('/api/market/scheduled/news').status_code==503
        assert len(calls)==2


def test_partial_source_result_is_visible(tmp_path,monkeypatch):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    monkeypatch.setattr(service,'_run_job',lambda job:service.store.update('jobs',job['id'],
        dict(status='partial',result={'successes':1,'failures':1,'sources':[{'source_id':'offline-good','status':'saved'},{'source_id':'offline-bad','status':'failed'}]})))
    with TestClient(app) as client:
        result=client.post('/api/market/scheduled/market')
        assert result.status_code==207
        assert result.json()['result']['successes']==1
        assert result.json()['result']['failures']==1


def test_source_failure_isolated_and_snapshots_deduplicate(tmp_path,monkeypatch):
    from london_product import sources
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    for identity in ['offline-good','offline-bad']:
        service.store.put('sources',identity,dict(id=identity,name=identity,url='https://example.test/'+identity,enabled=True,category='macro'))
    async def fetch(source,**kwargs):
        if source['id']=='offline-bad':raise TimeoutError('offline fault fixture')
        return dict(status_code=200,url=source['url'],content=b'<p>Offline fixture only. No live market data.</p>',media='text/html')
    monkeypatch.setattr(sources,'fetch_source',fetch)
    first=asyncio.run(service.refresh({}))
    second=asyncio.run(service.refresh({}))
    assert first['successes']==second['successes']==1
    assert first['failures']==second['failures']==1
    assert len(service.store.all('documents'))==1
    assert service.store.get('sources','offline-bad')['health']=='failed'
    assert service.store.get('sources','offline-good')['health']=='healthy'
    service.pool.shutdown()


def test_retry_keeps_original_monitoring_category(tmp_path,monkeypatch):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    calls=[]
    monkeypatch.setattr(service.pool,'submit',lambda fn,job:calls.append(job))
    old=service.store.put('jobs','original-news',dict(kind='refresh',category='news',status='partial'))
    with TestClient(app) as client:
        response=client.post('/api/market/jobs/'+old['id']+'/retry',headers={'Idempotency-Key':'retry-news'})
        assert response.status_code==202
        assert response.json()['category']=='news'
        assert calls[0]['category']=='news' and calls[0]['retry_of']==old['id']
        # Reusing that key for an all-source refresh is an explicit conflict.
        assert client.post('/api/market/refresh',headers={'Idempotency-Key':'retry-news'}).status_code==422


def test_daily_report_native_workflow_and_notification_missing(tmp_path,monkeypatch):
    monkeypatch.delenv('LONDON_NOTIFICATION_URL',raising=False)
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    with TestClient(app) as client:
        service.save_settings({'notifications_enabled':True})
        response=client.post('/api/market/scheduled/report-daily')
        assert response.status_code==207
        first=response.json()
        second=client.post('/api/market/scheduled/report-daily').json()
        assert first['status']=='partial' and first['report_status']=='succeeded'
        assert first['report_id']==second['report_id']
        assert first['run_id']==second['run_id']
        assert first['notification']['status']=='configuration_missing'
        assert len(service.store.all('reports'))==1
        assert len(service.store.all('jobs'))==1
        assert service.store.all('jobs')[0]['model_requests']==0
        service.save_settings({'monitoring_enabled':False})
        assert client.post('/api/market/scheduled/news').status_code==409


def test_scheduled_notification_failure_is_partial(tmp_path,monkeypatch):
    app=create_app(tmp_path,seed=False,scheduler=False)
    service=app.state.market
    with TestClient(app) as client:
        service.save_settings({'notifications_enabled':True})
        for state in ['failed','delivery_unknown']:
            monkeypatch.setattr(service,'notify',lambda report_id,state=state:dict(status=state))
            response=client.post('/api/market/scheduled/report-daily')
            assert response.status_code==207
            assert response.json()['status']=='partial'
            assert response.json()['report_status']=='succeeded'
            assert response.json()['notification']['status']==state
        monkeypatch.setattr(service,'notify',lambda report_id:dict(status='sent'))
        response=client.post('/api/market/scheduled/report-daily')
        assert response.status_code==200 and response.json()['status']=='succeeded'
        service.save_settings({'notifications_enabled':False})
        response=client.post('/api/market/scheduled/report-daily')
        assert response.status_code==200 and response.json()['notification']['status']=='disabled'
