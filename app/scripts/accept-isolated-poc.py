"""Current code, real saved/public data, native workflows/poller and local delivery.

Synthetic threshold arithmetic is in a separate directory and explicitly labelled.
No paid model/search or external notification is permitted.
"""
import hashlib,json,os,sqlite3,sys,threading,time,socket
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
OUT=Path(sys.argv[1]).resolve()
os.environ['LONDON_TAVILY_ENABLED']='0'
os.environ.pop('LONDON_NOTIFICATION_URL',None)
from london_product.runtime import create_app
from london_product.store import Store
from london_product.service import MarketService
from london_product.normalization import derive
from london_product.analysis_guard import review_analysis
import uvicorn
results=dict(at=datetime.now(timezone.utc).isoformat(),model_calls=0,paid_search_calls=0,notification_target='loopback only',checks={})
directory=OUT/'native-acceptance';directory.mkdir(exist_ok=True)
with sqlite3.connect((OUT/'isolated/market.sqlite3').as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(directory/'market.sqlite3') as dst:src.backup(dst)
app=create_app(directory,seed=False,scheduler=True,frontend_port=3102)
app.state.agent_os._scheduler_base_url='http://127.0.0.1:18782'
app.state.agent_os._scheduler_poll_interval=1
service=app.state.market
for run in range(2):
    job=service.submit('refresh',source_id='planning-api-city')
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        row=service.store.get('jobs',job['id'])
        if row['status'] not in ['queued','running']:break
        time.sleep(.2)
    results['checks']['real_acquisition_'+str(run)]=dict(job=row,documents=len(service.store.all('documents')),events=len(service.store.all('events')))
    results['checks']['real_acquisition_'+str(run)]['acceptance_status']='PASS' if row['status']=='succeeded' else 'BLOCKED'
    (OUT/'native-acquisition-checkpoint.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
results['checks']['real_monitor']=service.monitor_changes()
for name,question in [('A',"What is the recent trend in prime office rents in London's West End?"),
    ('B','Compare the City and Canary Wharf office markets in terms of rents, vacancy and leasing activity.'),
    ('C','What major office developments, leasing deals or market events should a London CRE manager pay attention to?'),
    ('F05','What are the latest notable changes in the Canary Wharf office market?')]:
    answer,citations=service.saved_answer(question)
    assert answer.strip()
    (OUT/('saved-answer-'+name+'.md')).write_text(answer,encoding='utf-8')
    results['checks']['saved_'+name]=dict(question=question,answer=answer,citations=citations,scope='Deterministic saved lookup; not live AI research')
report=service.generate_report('weekly',key='current-source-weekly')
(OUT/'market-brief-weekly.html').write_text(report['html'],encoding='utf-8')
(OUT/'market-brief-weekly.md').write_text(report['markdown'],encoding='utf-8')
scoped=service.generate_report('daily',key='current-source-city',geography='City')
assert scoped['geography']=='City' and scoped['window_days']==1
results['checks']['reports']=dict(weekly_id=report['id'],weekly_native_run=report['workflow_run_id'],city_id=scoped['id'],city_fact_ids=scoped['fact_ids'])
# Isolated synthetic arithmetic is never inserted in the real-source report.
fixture=MarketService(Store(OUT/'synthetic-threshold-only'))
common=dict(metric='vacancy',unit='percent',geography='City',status='validated',human_review_status='approved',source_id='synthetic-fixture',series='synthetic-fixture',definition='Synthetic overall office vacancy',basis='quarter_end',grade='all',method='synthetic-test',currency=None)
fixture.store.put('sources','synthetic-fixture',dict(id='synthetic-fixture',name='Synthetic fixture',allow_llm=True))
for identity,period,value in [('old','2026Q1','8'),('new','2026Q2','9')]:
    quote=f'SYNTHETIC TEST ONLY: City overall office vacancy {period}: {value} percent.'
    doc=fixture.store.snapshot(dict(id='synthetic-fixture'),'https://example.org/synthetic/'+identity,
        quote.encode(),'text/plain',[dict(text=quote,page=1,locator='fixture:1')])
    fixture.store.put('facts',identity,dict(common,id=identity,period=period,value=value,
        document_id=doc['id'],evidence=dict(quote=quote,page=1,locator='fixture:1')))
comparison=fixture.compare('old','new');assert comparison['status']=='comparable' and comparison['absolute_change']=='1'
threshold=fixture.monitor_changes();assert threshold['alerts']==1
assert fixture.monitor_changes()['event_ids']==threshold['event_ids']
results['checks']['synthetic_threshold']=dict(label='SYNTHETIC, not market evidence',comparison=comparison,threshold=threshold,unique_event_count=len(fixture.store.all('events')))
fixture.pool.shutdown()
received=[]
class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        received.append(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
        self.send_response(200);self.end_headers();self.wfile.write(b'OK')
    def log_message(self,*args):pass
receiver=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
threading.Thread(target=receiver.serve_forever,daemon=True).start()
os.environ['LONDON_NOTIFICATION_URL']=f'json://127.0.0.1:{receiver.server_port}/isolated-only'
service.save_settings(dict(monitoring_enabled=True,notifications_enabled=True))
# After free acquisition, prevent every external connection, including a model.
original_connect=socket.socket.connect
def connect(sock,address):
    if isinstance(address,tuple) and address[0] not in ['127.0.0.1','localhost','::1']:raise RuntimeError('EXTERNAL_NETWORK_DISABLED_IN_LOCAL_ACCEPTANCE')
    return original_connect(sock,address)
socket.socket.connect=connect
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18782,log_level='warning'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
try:
    for _ in range(150):
        if server.started:break
        time.sleep(.1)
    assert server.started
    manager=service.schedule_manager
    for schedule in manager.list():manager.disable(schedule.id)
    schedule=manager.create(name='delivery-once-'+str(time.time_ns()),cron='* * * * *',endpoint='/api/market/scheduled/report-daily',payload={},max_retries=0,timeout_seconds=40)
    manager.db.update_schedule(schedule.id,next_run_at=int(time.time())-1)
    for _ in range(400):
        runs=manager.db.get_schedule_runs(schedule.id)[0]
        if runs and runs[0].get('status') in ['completed','failed','succeeded','success']:break
        time.sleep(.1)
    manager.disable(schedule.id)
    runs=manager.db.get_schedule_runs(schedule.id)[0]
    assert runs and runs[0].get('status') in ['completed','succeeded','success'],runs
    notifications=service.store.all('notifications')
    sent=next(n for n in notifications if n.get('status')=='sent' and n.get('started_at','')>=results['at'])
    before=len(received);duplicate=service.notify(sent['report_id'])
    assert len(received)==before and duplicate.get('deduplicated')
    assert received and sent.get('recipient_delivery_confirmed') is False
    results['checks']['scheduler_and_local_delivery']=dict(schedule=schedule.to_dict(),runs=runs,notification=sent,
        received_count=len(received),received_payload_sha256=[hashlib.sha256(p.encode()).hexdigest() for p in received],
        deduplicated=duplicate.get('deduplicated'),scope='Real native due poll -> HTTP -> report workflow -> Apprise -> localhost receiver. Not email/Telegram recipient verification.')
    results['result']='PARTIAL: free/saved monitoring and loopback delivery exercised. This harness does not test a model or real recipient delivery. Threshold change is a separate labelled synthetic scenario.'
finally:
    server.should_exit=True;thread.join(10);receiver.shutdown();receiver.server_close()
    (OUT/'isolated-acceptance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (OUT/('acceptance-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(result=results.get('result'),checks=list(results['checks']),notifications_received=len(received)),ensure_ascii=False))
