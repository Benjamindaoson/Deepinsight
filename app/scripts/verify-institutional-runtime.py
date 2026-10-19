"""Read-only final acceptance receipts; the model POST is blocked before execution."""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from london_product.store import Store, now

OUT = ROOT / 'docs/delivery/institutional-report-acceptance'
PHASE = ROOT / 'docs/delivery/claim-evidence-binding-phase1'
base = 'http://127.0.0.1:7785'

def get(path):
    with urllib.request.urlopen(base + path, timeout=30) as response:
        return json.load(response)

identity = get('/api/market/runtime-identity')
assert not any(identity[k] for k in ['paid_allowed', 'scheduler', 'notifications'])
current = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (ROOT / 'app/london_product').glob('*.py')}
assert identity['source_sha256'] == current, 'RUNNING_SOURCE_IDENTITY_DIFFERS'
store = Store(OUT / 'runtime')
try:
    baseline = json.loads((OUT / 'review-baseline.json').read_text(encoding='utf-8'))
    changes = []
    for key, original in baseline.items():
        table, rid = key.split(':', 1)
        row = store.get(table, rid)
        if not row or {k: row.get(k) for k in original} != original: changes.append(key)
    assert not changes, 'REVIEW_STATE_CHANGED'
    reports = []
    for rid in ['bc145e16-f6cf-407e-8072-895a87a02b80', '645449ac-b09a-4a20-8040-b9baf50cdc0a']:
        artifact = get('/api/market/reports/' + rid + '?format=json')
        formats = {}
        for fmt in ['html', 'markdown']:
            with urllib.request.urlopen(base + '/api/market/reports/' + rid + '?format=' + fmt, timeout=30) as response:
                content = response.read()
                formats[fmt] = dict(status=response.status, bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
                assert artifact['title'].encode() in content
        reports.append(dict(report_id=rid, status=artifact['generation_status'], model_status=(artifact.get('ai_analysis') or {}).get('status'),
            ready_charts=sum(c['status'] == 'ready' for c in artifact['charts']),
            scoped_observations=len(artifact['market_snapshot']), related_observations=len(artifact.get('related_observations', [])),
            source_quotations=len(artifact['evidence']), formats=formats))
    request = urllib.request.Request(base + '/api/market/ask', data=json.dumps(dict(message='DO NOT EXECUTE: paid-boundary check', mode='agent')).encode(), headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(request, timeout=10)
        raise AssertionError('PAID_BOUNDARY_NOT_ENFORCED')
    except urllib.error.HTTPError as exc:
        assert exc.code == 409
    receipt = dict(at=now(), running_source_matches=True, runtime=identity, existing_review_records_checked=len(baseline),
        existing_review_state_changes=changes, reports=reports, paid_boundary_status=409, additional_model_requests=0)
    (PHASE / 'runtime-verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'runtime'}, ensure_ascii=False, indent=2))
finally:
    store.engine.dispose()
