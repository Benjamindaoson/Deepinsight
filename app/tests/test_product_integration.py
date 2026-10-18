import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from london_product.store import Store
from london_product.service import MarketService


def test_apprise_real_local_http_and_delivery_dedup(tmp_path,monkeypatch):
    receipts=[]
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            receipts.append(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(200);self.end_headers();self.wfile.write(b'OK')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        monkeypatch.setenv('LONDON_NOTIFICATION_URL',f'json://127.0.0.1:{server.server_port}/notification')
        service=MarketService(Store(tmp_path));service.save_settings({'notifications_enabled':True})
        report=service.report('weekly')
        assert service.notify(report['id'])['status']=='sent'
        assert service.notify(report['id'])['deduplicated']
        assert len(receipts)==1 and 'London' in receipts[0].decode()
    finally:server.shutdown();server.server_close()


def test_native_failed_output_never_becomes_succeeded(tmp_path):
    service=MarketService(Store(tmp_path))
    service.workflow=SimpleNamespace(run=lambda _:SimpleNamespace(content='Step skipped due to error',run_id='actual-test-run',status='ERROR'))
    job=service.store.put('jobs','failed-native',{'kind':'refresh','status':'queued'})
    service._run_job(job)
    result=service.store.get('jobs',job['id'])
    assert result['status']=='failed' and result['run_id']=='actual-test-run'


def test_geo_search_keeps_exact_comparison_dimensions(tmp_path):
    service=MarketService(Store(tmp_path))
    service.store.put('facts','qualified',dict(metric='rent',geography='City (BNP source-defined office submarket)',value='95',status='needs_review'))
    found=service.facts(geography='City')['items']
    assert len(found)==1 and found[0]['geography']=='City (BNP source-defined office submarket)'
