"""One real native scheduler occurrence and one GPE fetch; no models/notifications.

Run only after the product backend has been restarted with the repaired code.
The existing daily cron is retained. Only its next_run_at is moved forward once.
"""
import hashlib
import json
import sys
import time
from pathlib import Path
import httpx

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from agno.db.sqlite import SqliteDb
from agno.scheduler import ScheduleManager
from london_product.store import Store

OUT=APP/'data/product/evidence/market-closure-20261018/monitor'
DATA=APP/'data/product'

def dump(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def main():
    with httpx.Client(base_url='http://127.0.0.1:7780',timeout=30,trust_env=False) as client:
        settings=client.get('/api/market/settings').raise_for_status().json()
        # Fail closed: this validation must never send an external notification.
        assert settings['monitoring_enabled'] and not settings['notifications_enabled']
        assert not settings['notification_configured']
        store=Store(DATA)
        facts_before=store.all('facts')
        originals={d['id']:dict(path=d['path'],sha256=d['sha256']) for d in store.all('documents')}
        sources=client.get('/api/market/sources').raise_for_status().json()['items']
        gpe=next(s for s in sources if s['id']=='gpe')
        assert gpe.get('enabled')
        dump('gpe-before.json',gpe)
        job=client.post('/api/market/sources/gpe/refresh',headers={'Idempotency-Key':'market-closure-gpe-20261018'}).raise_for_status().json()
        deadline=time.monotonic()+180
        while job['status'] in ['queued','running'] and time.monotonic()<deadline:
            time.sleep(1)
            job=client.get('/api/market/jobs/'+job['id']).raise_for_status().json()
        dump('gpe-real-refresh.json',job)
        assert job['status'] not in ['queued','running'],'GPE_REFRESH_TIMEOUT'
        assert job.get('run_id'),'GPE_WORKFLOW_ID_MISSING'
        # External access may legitimately fail; record it without synthesizing success.
        native=SqliteDb(id='london-product',db_file=str(DATA/'agno.sqlite3'))
        manager=ScheduleManager(native)
        schedules=manager.list()
        daily=next(s for s in schedules if s.name=='london-report-daily')
        assert daily.enabled and daily.endpoint=='/api/market/scheduled/report-daily'
        assert len([s for s in schedules if s.name.startswith('london-')])==4
        dump('schedules-before.json',[s.to_dict() for s in schedules])
        previous_ids={r.id for r in manager.get_runs(daily.id)}
        started=time.time()
        due=int(started)+5
        manager.update(daily.id,next_run_at=due)
        dump('trigger-receipt.json',dict(method='Move existing daily next_run_at only; native poller claims it',schedule_id=daily.id,due_at=due,started_at=started,cron_unchanged=daily.cron_expr))
        try:
            deadline=time.monotonic()+90
            observed=None
            while time.monotonic()<deadline:
                candidates=[r for r in manager.get_runs(daily.id) if r.id not in previous_ids and r.status!='running']
                if candidates:
                    observed=candidates[0];break
                time.sleep(1)
            assert observed is not None,'NATIVE_POLLER_DID_NOT_COMPLETE_WITHIN_90_SECONDS'
            dump('native-schedule-run.json',observed.to_dict())
            assert observed.status=='success' and observed.status_code==200
        finally:
            after=manager.get(daily.id)
            # Never alter the cron. Restore the original due time only if it is
            # still in the future; otherwise preserve the poller's next cron.
            if daily.next_run_at and daily.next_run_at>time.time():
                manager.update(daily.id,next_run_at=daily.next_run_at)
            assert after.cron_expr==daily.cron_expr
        day=time.strftime('%Y-%m-%d',time.gmtime())
        report=store.get('reports','report:scheduled-daily-'+day)
        assert report and report.get('workflow_run_id')
        report_job=store.get('jobs','report:scheduled-daily-'+day)
        assert report_job and report_job['status']=='succeeded' and report_job['model_requests']==0
        dump('scheduled-report-job.json',report_job)
        dump('scheduled-report.json',report)
        sessions=native.get_sessions(component_id='london-report-workflow',deserialize=False)
        raw_sessions=sessions[0] if isinstance(sessions,tuple) else sessions
        matching=[s for s in raw_sessions if report['workflow_run_id'] in json.dumps(s,default=str)]
        assert matching,'WORKFLOW_RUN_NOT_PERSISTED'
        dump('native-workflow-session.json',matching)
        for fmt in ['markdown','html']:
            response=client.get('/api/market/reports/'+report['id'],params={'format':fmt}).raise_for_status()
            (OUT/('scheduled-daily.'+('md' if fmt=='markdown' else 'html'))).write_text(response.text,encoding='utf-8')
        # Confirm native report idempotence, without another scheduler occurrence.
        repeated=client.post('/api/market/scheduled/report-daily').raise_for_status().json()
        assert repeated['report_id']==report['id'] and repeated['run_id']==report['workflow_run_id']
        dump('report-idempotency.json',repeated)
        missing=client.post('/api/market/notifications',json={'report_id':report['id']}).raise_for_status().json()
        assert missing['status']=='configuration_missing' and missing['attempts']==0
        dump('notification-configuration-missing.json',missing)
        dump('schedules-after.json',[s.to_dict() for s in manager.list()])
        assert facts_before==store.all('facts'),'EXISTING_FACTS_CHANGED'
        changed=[]
        for identity,doc in originals.items():
            if hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()!=doc['sha256']:
                changed.append(identity)
        assert not changed,'ORIGINAL_SNAPSHOT_HASH_CHANGED'
        dump('verification-summary.json',dict(native_scheduler='PASS',schedule_run_id=observed.id,workflow_run_id=report['workflow_run_id'],report_id=report['id'],gpe_refresh_status=job['status'],gpe_job_id=job['id'],gpe_run_id=job['run_id'],notification_status=missing['status'],model_requests=0,external_notifications=0,original_facts_unchanged=True,original_document_count=len(originals),original_hashes_unchanged=True,elapsed_seconds=round(time.time()-started,3)))
        print(json.dumps(json.loads((OUT/'verification-summary.json').read_text(encoding='utf-8')),ensure_ascii=False))

if __name__=='__main__':
    main()
