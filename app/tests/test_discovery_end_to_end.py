"""Offline provider/original fixtures plus REAL loopback HTTP Apprise delivery.

Never a live Tavily or external-channel acceptance claim.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from london_product.runtime import create_app
from london_product.sources import catalog


def test_discovery_native_workflow_report_and_loopback_notification(tmp_path, monkeypatch):
    from london_product import discovery, sources
    received, searches = [], []
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers['Content-Length'])).decode())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'accepted by local fixture')
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv('LONDON_NOTIFICATION_URL', f'json://127.0.0.1:{server.server_port}/loopback-only')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'offline-not-a-real-key')
    def search(request):
        searches.append(1)
        return httpx.Response(200, json={'results': [{'url': 'https://www.gpe.co.uk/news-media/news/2026/offline-lease/'}]})
    monkeypatch.setattr(discovery, '_transport', lambda: httpx.MockTransport(search))
    async def fetch(source, **kw):
        content = b'<main>Listing only.</main>' if source['url'].endswith('/news/') else b'<main><h1>Offline London office lease</h1><p>This is an offline fixture: London office leasing terms remain subject to review.</p></main>'
        return dict(status_code=200, url=source['url'], content=content, media='text/html')
    monkeypatch.setattr(sources, 'fetch_source', fetch)
    app = create_app(tmp_path, seed=False, scheduler=False)
    service = app.state.market
    service.store.put('sources', 'gpe', next(s for s in catalog() if s['id'] == 'gpe'))
    try:
        with TestClient(app) as client:
            service.save_settings({'notifications_enabled': True})
            response = client.post('/api/market/scheduled/news', headers={'Idempotency-Key': 'offline-one'})
            assert response.status_code == 200
            job = response.json()
            assert job['run_id'] and job['status'] == 'succeeded'
            replay = client.post('/api/market/scheduled/news', headers={'Idempotency-Key': 'offline-one'}).json()
            assert replay['id'] == job['id']
            retry = client.post('/api/market/scheduled/news', headers={'Idempotency-Key': 'offline-two'}).json()
            assert retry['status'] == 'succeeded'
            events = [e for e in service.store.all('events') if e['kind'] != 'source_update']
            assert len(searches) == 1 and len(events) == 1
            assert len(service.store.all('events')) == 2  # existing listing-change record retained
            event = events[0]
            assert event['status'] == 'pending_review' and event['evidence']['locator']
            report = service.generate_report('weekly', key='offline-report')
            assert report['workflow_run_id']
            notice = client.post('/api/market/notifications', json={'report_id': report['id']}).json()
            second = client.post('/api/market/notifications', json={'report_id': report['id']}).json()
            assert notice['status'] == 'sent' and second['deduplicated'] and len(received) == 1
            assert notice['receipt_kind'] == 'apprise_transport_acceptance'
            assert 'Offline London office lease' in received[0]
            assert 'pending_review' in received[0]
            evidence = dict(scope='MOCK Tavily and source; REAL localhost HTTP Apprise only',
                real_tavily_requests=0, mock_search_requests=len(searches), model_requests=0,
                monitoring_job=job, event=event, report_id=report['id'], report_run_id=report['workflow_run_id'],
                notification=notice, duplicate=second, received_http_posts=received)
            # Deliberately labelled fixture, kept outside the real business DB.
            target = Path(__file__).parents[1] / 'data/product/evidence/news-discovery-notifications-20261018'
            target.mkdir(parents=True, exist_ok=True)
            (target / 'offline-chain-loopback-receipt.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        server.shutdown()
        server.server_close()
