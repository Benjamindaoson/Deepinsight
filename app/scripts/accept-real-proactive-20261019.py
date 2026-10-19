"""Real snapshots + existing Apprise -> loopback only. No LLM or review writes."""
import hashlib,json,os,socket,sys,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.service import MarketService
from london_product.chat_report import read_report,render_markdown

OUT=ROOT/'docs/delivery/real-proactive-20261019'
if (OUT/'ACCEPTANCE_RECEIPT.json').exists():raise SystemExit('Preserve prior acceptance receipt; do not replay implicitly')
store=Store(OUT/'runtime');service=MarketService(store)
baseline=json.loads((OUT/'review-baseline.json').read_text(encoding='utf-8'))
model_calls=[]
def no_model():
    model_calls.append(True);raise AssertionError('FREE_ACCEPTANCE_MODEL_DISABLED')
service.agent_factory=no_model
original_connect=socket.socket.connect
def loopback_only(sock,address):
    if not isinstance(address,tuple) or address[0] not in ['127.0.0.1','::1','localhost']:
        raise RuntimeError('ACCEPTANCE_EXTERNAL_NETWORK_DISABLED')
    return original_connect(sock,address)
socket.socket.connect=loopback_only
received=[]
class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        data=self.rfile.read(int(self.headers.get('Content-Length','0')))
        received.append(dict(path=self.path,payload=json.loads(data),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        # Exercise a definite local refusal, then one explicit operator retry.
        self.send_response(503 if len(received)==1 else 200);self.end_headers();self.wfile.write(b'isolated receiver')
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
previous=os.environ.get('LONDON_NOTIFICATION_URL')
os.environ['LONDON_NOTIFICATION_URL']=f'json://127.0.0.1:{server.server_port}'
try:
    before=service.settings();assert before['vacancy_threshold_pp']==0.5
    service.save_settings(dict(monitor_analysis_enabled=False,notifications_enabled=False))
    monitor=service.monitor_changes(detection_context='historical_replay')
    ids={'07ded13f-ec67-40b8-a87d-faa66d017afe','a44bf53f-2f7c-4103-b04a-6a0e1212c156'}
    decision=next(d for d in monitor['decisions'] if {d.get('old_id'),d.get('new_id')}==ids)
    assert decision['status']=='below_threshold' and decision['value']=='-0.1' and decision['threshold']==0.5
    assert monitor['alerts']==0
    intelligence=service.monitor_intelligence(monitor,detection_context='historical_replay')
    assert intelligence==[] and not received and not model_calls
    rid='b815e22e-459d-437a-adbc-e22ccecd4a4d'
    report=read_report(store,rid);assert report['generation_status']=='partial' and report['ai_analysis'] is None
    service.save_settings(dict(notifications_enabled=True))
    first=service.notify(rid);assert first['status']=='failed' and len(received)==1
    second=service.notify(rid);assert second['status']=='sent' and len(received)==2
    third=service.notify(rid);assert third.get('deduplicated') and third['id']==second['id'] and len(received)==2
    body=received[-1]['payload']['message']
    expected=[e for e in report['evidence'] if e['id'] in ids]
    for e in expected:
        assert e['url'] in body and e['document_sha256'] in body and e['period'] in body
    assert all(x in body for x in ['6.8','6.7',rid,'partial','page 5','not the full report'])
    assert len(body.encode('utf-8'))<=12000 and not model_calls
    assert 'vacancy · West End: 2026Q1 → 2026Q2 = -0.10 pp' in render_markdown(report)
    after={f['id']:{k:f.get(k) for k in ['status','human_review_status']} for f in store.all('facts')}
    assert after==baseline
    service.save_settings(dict(notifications_enabled=False))
    receipt=dict(at=now(),model_requests=0,formal_database_writes=0,review_state_changes=[],
        real_monitoring=dict(status='PASS_BELOW_THRESHOLD',historical_replay=True,result=monitor,intelligence=intelligence),
        isolated_transport=dict(status='PASS_REAL_REPORT_LOOPBACK',manual=True,automatic_business_alert=False,
            report_id=rid,receiver='127.0.0.1 only',first=first,explicit_retry=second,deduplicated=third,
            received_requests=len(received),body_utf8_bytes=len(body.encode('utf-8')),recipient_delivery_confirmed=False),
        complete_proactive_ai_business=dict(status='BLOCKED',reasons=['Current reviewed historical change is below existing significance threshold',
            'No additional model calls authorized; most recent real provider attempt rejected for insufficient quota']),
        settings_at_close=dict(notifications_enabled=False,monitor_analysis_enabled=False))
    (OUT/'ACCEPTANCE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'LOOPBACK_RECEIVED.json').write_text(json.dumps(received,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'notification-summary.txt').write_text(body,encoding='utf-8')
    print(json.dumps(dict(monitor=decision,first=first['status'],explicit_retry=second['status'],deduplicated=third['deduplicated'],
        body_bytes=len(body.encode('utf-8')),requests=len(received),model_calls=len(model_calls),review_changes=0),ensure_ascii=False))
finally:
    service.save_settings(dict(notifications_enabled=False,monitor_analysis_enabled=False))
    if previous is None:os.environ.pop('LONDON_NOTIFICATION_URL',None)
    else:os.environ['LONDON_NOTIFICATION_URL']=previous
    socket.socket.connect=original_connect;server.shutdown();server.server_close()
    service.pool.shutdown(wait=True);store.engine.dispose()
