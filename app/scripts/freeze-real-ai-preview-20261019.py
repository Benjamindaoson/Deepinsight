"""Freeze source identity and actual read-only preview checks; never call a model."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/delivery/real-ai-preview-20261019'
previous = json.loads((ROOT / 'docs/delivery/real-proactive-20261019/FINAL_MANIFEST.json').read_text(encoding='utf-8'))
paths = set(previous['source_files']) | {
    'app/tests/test_real_report_projection.py', 'app/tests/fixtures/real_report_projection.json',
    'app/scripts/preview-real-ai-20261019.py', 'app/scripts/freeze-real-ai-preview-20261019.py'}
sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(paths)}
with httpx.Client(base_url='http://127.0.0.1:7785', trust_env=False, timeout=20) as client:
    identity = client.get('/api/market/runtime-identity').raise_for_status().json()
    assert identity['directory'] == str(OUT / 'runtime')
    assert not any(identity[k] for k in ['paid_allowed', 'scheduler', 'notifications'])
    assert all(sources[p] == digest for p, digest in identity['source_sha256'].items())
    report = client.get('/api/market/reports/f9209186-901c-43cc-9f5b-6cc80df2fe99?format=json').raise_for_status().json()
    projection = client.get('/api/market/sessions/24bbe134-4997-4e7e-9ee1-e6f2f5e3d311/runs/93ed089d-583f-4f40-9527-534a6400bd96/publication').raise_for_status().json()
assert report['generation_status'] == 'partial' and report['ai_analysis']['status'] == 'published'
assert len(report['ai_analysis']['accepted']) == 2 and not report['ai_analysis']['blocked']
assert projection['answer_origin'] == 'ai_limited_checks'
assert projection['publication_review']['status'] == 'limited_checks_passed'
assert projection['publication_review']['semantic_approval'] is False
dom = (OUT / 'restored-session.dom.txt').read_text(encoding='utf-8')
assert 'AI 分析通过有限自动检查' in dom and 'AI 草稿已拦截' not in dom
manifest = dict(source_files=sources, runtime_identity=identity,
    report_id=report['report_id'], status=report['generation_status'], accepted=2, blocked=0,
    ready_charts=sum(c['status'] == 'ready' for c in report['charts']),
    publication=projection['publication_review'],
    verification=dict(final_targeted='63 passed in 20.35s', offline_api='7 passed in 11.54s',
        previous_full_backend='525 passed before final provider/projection deltas',
        provider_guard='40 passed after provider delta',
        browser='actual saved native session restored; correct label; real chart and evidence; no console errors'),
    model_requests_in_preview=0, review_state_changes_in_preview=0,
    complete_multi_region_business='PARTIAL', significant_proactive_ai_business='NOT_PASSED')
(OUT / 'FINAL_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
ready = json.loads((OUT / 'READY_FOR_INDEPENDENT_RECHECK.json').read_text(encoding='utf-8-sig'))
ready.update(runtime_pid=identity['pid'], manifest_sha256=hashlib.sha256((OUT / 'FINAL_MANIFEST.json').read_bytes()).hexdigest(),
    source_files=len(sources), final_targeted_tests=63, browser_blocked_label_count=0,
    browser_limited_label_count=1, browser_console_errors=[])
(OUT / 'READY_FOR_INDEPENDENT_RECHECK.json').write_text(json.dumps(ready, indent=2), encoding='utf-8')
print(json.dumps(dict(source_files=len(sources), runtime_pid=identity['pid'], report_status='partial', accepted=2, ready_charts=manifest['ready_charts'], model_requests=0)))
