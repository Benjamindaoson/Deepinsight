"""Actual API, original integrity, saved A-E scenarios and process-reopen checks.

This script makes no model or external notification calls. Synthetic signal
evidence is stored separately from the real-source demo runtime.
"""
import hashlib,json,os,sqlite3,sys,subprocess,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
OUT=ROOT/'docs/delivery/final-delivery-20261019'
os.environ['LONDON_TAVILY_ENABLED']='0';os.environ['LONDON_JEV_ROUTING_ENABLED']='0';os.environ.pop('LONDON_NOTIFICATION_URL',None)
from fastapi.testclient import TestClient
from london_product.runtime import create_app
from london_product.store import Store,now
from london_product.service import MarketService
from london_product.safe_answer import safe_evidence
directory=OUT/'demo-runtime'
if directory.exists():raise SystemExit('Preserve prior functional execution; choose a new receipt directory')
directory.mkdir()
with sqlite3.connect(OUT/'baseline/real-source/market.sqlite3') as src,sqlite3.connect(directory/'market.sqlite3') as dst:src.backup(dst)
store=Store(directory)
originals=[]
for doc in store.all('documents'):
    content=Path(doc['path']).read_bytes();assert hashlib.sha256(content).hexdigest()==doc['sha256']
    target=store.artifacts/(doc['sha256']+Path(doc['path']).suffix);target.write_bytes(content)
    store.update('documents',doc['id'],dict(path=str(target)))
    originals.append(dict(id=doc['id'],url=doc.get('url'),sha256=doc['sha256'],path=str(target)))
store.engine.dispose()
app=create_app(directory,seed=False,scheduler=False,frontend_port=3106);svc=app.state.market
receipt=dict(started_at=now(),model_calls=0,external_notifications=0,originals=originals,checks={},saved_cases={})
def save(): (OUT/'functional-acceptance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
try:
 with TestClient(app) as client:
    endpoints=['overview','facts','events','documents','sources','reports','jobs','settings','coverage','notifications/configuration']
    for endpoint in endpoints:
        r=client.get('/api/market/'+endpoint);assert r.status_code==200,(endpoint,r.status_code)
        receipt['checks']['GET '+endpoint]=dict(status='PASS',http=r.status_code)
    scopes=[('A','What was West End overall office vacancy in Q2 2026?'),
        ('B','Compare West End overall vacancy in Q1 and Q2 2026'),
        ('C','Show London office developments and leasing activity for Q2 2026'),
        ('D','Exact Canary Wharf Grade A vacancy for October 2026'),
        ('E','Prepare a Q2 2026 City, West End and Canary Wharf office market report covering rent vacancy availability take-up and development pipeline')]
    for label,question in scopes:
        r=client.post('/api/market/ask',json=dict(message=question,mode='saved'))
        events=[json.loads(x[6:]) for x in r.text.splitlines() if x.startswith('data: ')]
        terminal=next(e for e in reversed(events) if e.get('type') in ['done','error'])
        assert terminal['type']=='done',(label,terminal)
        artifact=next(e['report'] for e in events if e.get('type')=='report')
        receipt['saved_cases'][label]=dict(question=question,final=terminal,artifact=artifact)
        (OUT/('saved-'+label+'.json')).write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    a=receipt['saved_cases']['A']['artifact'];b=receipt['saved_cases']['B']['artifact'];d=receipt['saved_cases']['D']['artifact']
    assert any(x['value']=='6.7' and x['review_status']=='approved' for x in a['market_snapshot'])
    assert b['calculations'][0]['absolute_change']=='-0.1' and b['calculations'][0]['change_unit']=='pp'
    assert b['scope']['requested_periods']==['2026Q1','2026Q2']
    assert d['generation_status']=='insufficient_evidence'
    rid=b['report_id'];receipt['demo_report_id']=rid
    for fmt in ['json','html','markdown']:
        r=client.get('/api/market/reports/'+rid+'?format='+fmt);assert r.status_code==200
        (OUT/('West-End-vacancy-report.'+('md' if fmt=='markdown' else fmt))).write_text(r.text,encoding='utf-8')
    compare=client.post('/api/market/compare',json=dict(old_id='BNP-2026Q1-RENT',new_id='BNP-2026Q2-RENT')).json()
    assert compare['status']=='not_comparable' and compare['absolute_change'] is None
    receipt['checks']['unannualized_rent_rejected']=compare
    invalid=client.post('/api/market/ask',json=dict(message='   ',mode='saved'));assert invalid.status_code==422
    receipt['checks']['invalid_input']=dict(status='PASS',http=invalid.status_code)
    coverage=client.get('/api/market/coverage').json();receipt['coverage']=coverage
    receipt['data_counts']={t:len(svc.store.all(t)) for t in ['sources','documents','facts','events','reports','jobs']}
    receipt['effective_approved_facts']=[f['id'] for f in svc.facts(limit=500)['items'] if f.get('human_review_status')=='approved']
 save()
 # A separate Python interpreter reopens persisted SQLite and checks the exact
 # report, not an in-memory object or a cached TestClient response.
 code="import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); x=json.loads(d.execute('select payload from reports where id=?',(sys.argv[2],)).fetchone()[0]); assert x['artifact']['scope']['requested_periods']==['2026Q1','2026Q2']; print(json.dumps(dict(report_id=x['id'],calculations=x['artifact']['calculations'])))"
 result=subprocess.run([sys.executable,'-c',code,str(directory/'market.sqlite3'),rid],capture_output=True,text=True,check=True)
 receipt['checks']['fresh_process_persistence']=dict(status='PASS',result=json.loads(result.stdout))
 # Synthetic threshold -> report -> real Apprise -> loopback HTTP receiver.
 synthetic=MarketService(Store(OUT/'synthetic-complete-monitor'))
 source=dict(id='synthetic',name='SYNTHETIC TEST ONLY',allow_llm=True)
 synthetic.store.put('sources','synthetic',source)
 for identity,period,value in [('old','2026Q1','8'),('new','2026Q2','9')]:
    quote=f'SYNTHETIC TEST ONLY: City vacancy {period} is {value} percent.'
    doc=synthetic.store.snapshot(source,'https://example.org/synthetic/'+identity,quote.encode(),'text/plain',[dict(text=quote,page=1,locator='test:1')])
    synthetic.store.put('facts',identity,dict(id=identity,metric='vacancy',value=value,unit='percent',geography='City',period=period,
        source_id='synthetic',series='synthetic',definition='Synthetic vacant office stock share',basis='quarter_end',grade='all',method='synthetic',currency=None,
        document_id=doc['id'],evidence=dict(quote=quote,page=1,locator='test:1'),status='validated',human_review_status='approved'))
 received=[]
 class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        received.append(self.rfile.read(int(self.headers['Content-Length'])).decode());self.send_response(200);self.end_headers()
    def log_message(self,*args):pass
 receiver=ThreadingHTTPServer(('127.0.0.1',0),Receiver);threading.Thread(target=receiver.serve_forever,daemon=True).start()
 try:
    os.environ['LONDON_NOTIFICATION_URL']=f'json://127.0.0.1:{receiver.server_port}/SYNTHETIC'
    synthetic.save_settings(dict(notifications_enabled=True,monitor_analysis_enabled=False))
    detected=synthetic.monitor_changes(detection_context='historical_replay');assert detected['alerts']==1
    reports=synthetic.monitor_intelligence(detected,detection_context='historical_replay')
    assert len(received)==1 and reports[0]['notification_status']=='sent'
    again=synthetic.monitor_intelligence(synthetic.monitor_changes(detection_context='historical_replay'))
    assert again[0]['deduplicated'] and len(received)==1
    receipt['checks']['synthetic_monitor_report_transport']=dict(label='SYNTHETIC TEST ONLY, not a market change or real recipient delivery',status='PASS',detected=detected,reports=reports,repeat=again,received_count=len(received),persisted_event=synthetic.store.get('events',detected['event_ids'][0]))
 finally:
    receiver.shutdown();receiver.server_close();synthetic.pool.shutdown();synthetic.store.engine.dispose();os.environ.pop('LONDON_NOTIFICATION_URL',None)
 receipt['finished_at']=now();receipt['engineering_result']='PASS for checks asserted here; real AI and broad market coverage are graded separately';save()
 print(json.dumps(dict(checks=len(receipt['checks']),report_id=rid,effective_approved=receipt['effective_approved_facts'],result=receipt['engineering_result'])))
except Exception as exc:
 receipt['failure']=dict(type=type(exc).__name__,message=str(exc));save();raise
