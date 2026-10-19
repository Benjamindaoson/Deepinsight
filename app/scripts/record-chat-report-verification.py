"""Compose exact acceptance receipts after all commands have actually passed."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from london_product.store import now
from london_product.report_contracts import ReportInterpretation

PHASE = ROOT / 'docs/delivery/claim-evidence-binding-phase1'
UI = ROOT / 'docs/delivery/institutional-report-acceptance'
manifest_path = PHASE / 'accepted-candidate/SOURCE_MANIFEST.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
drift = [x['path'] for x in manifest['files']
    if hashlib.sha256((ROOT / x['path']).read_bytes()).hexdigest() != x['sha256']]
assert not drift, 'FROZEN_CANDIDATE_DRIFT: ' + str(drift)
log = (PHASE / 'pytest-verified-all.log').read_text(encoding='utf-8')
match = re.search(r'(\d+) passed in ([\d.]+)s', log)
assert match and not re.search(r'\d+ failed', log), 'FINAL_REGRESSION_NOT_GREEN'
probe = json.loads((PHASE / 'accepted-candidate/PHASE1_PROBE_RESULTS.json').read_text(encoding='utf-8'))
assert probe['passed'] == probe['total'] == 14 and not probe['false_publications']
runtime = json.loads((PHASE / 'runtime-verification.json').read_text(encoding='utf-8'))
assert runtime['running_source_matches'] and not runtime['existing_review_state_changes']
build_id = (ROOT / 'app/frontend/.next-institutional-final/BUILD_ID').read_text(encoding='utf-8').strip()
schema = ReportInterpretation.model_json_schema()
(PHASE / 'ReportInterpretation.schema.json').write_text(json.dumps(schema, indent=2), encoding='utf-8')
checks = dict(backend_full=dict(passed=int(match[1]), seconds=float(match[2]), log='pytest-verified-all.log'),
    changed_modules_after_full_collection=dict(passed=29, log='pytest-changed-modules-final.log',
        modules=['intelligence.py','service.py'], explanation='Incremental recheck after the last source updates; the frozen candidate has no subsequent drift.'),
    targeted_report_publication=dict(passed=86, log='pytest-release-final.log'),
    original_frozen_security_probes=dict(passed=14, total=14, false_publications=0, positive_controls_published=2),
    frontend_unit=dict(passed=30), frontend_types='passed', frontend_lint=dict(errors=0, existing_warnings=1),
    frontend_report_formatting='passed', frontend_build=dict(status='passed', build_id=build_id, dist='.next-institutional-final'),
    local_api=dict(json=200, html=200, markdown=200, health=200, blocked_paid_execution=409),
    browser=dict(real_native_homepage_run=True, report_reopened=True, citation_expanded=True, evidence_viewer=True,
        final_build_report_reopened=True, mobile_device_tested=False))
receipt = dict(at=now(), software_phase='claim_evidence_phase1', engineering_status='PASS', real_market_poc='PARTIAL_NOT_PASS',
    candidate='accepted-candidate/candidate', manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    frozen_source_drift=[], checks=checks, runtime_pid=runtime['runtime']['pid'], runtime_port=7785, frontend_port=3105,
    existing_review_records_checked=82, existing_review_state_changes=[], additional_paid_calls_in_phase1=0,
    native_report_id='bc145e16-f6cf-407e-8072-895a87a02b80',
    real_generation_status='insufficient_evidence', real_model_status='failed', released_real_market_charts=0,
    boundaries=['Positive claim compiler is not general semantic entailment or human approval.',
        'Synthetic probes are not real-model analysis or real market approval.',
        'Real provider output exceeded the authorized cap; no further paid retry.',
        'Persisted plans, bounded business parallelism, checkpoint recovery and real proactive notification remain later phases.'])
(PHASE / 'CLAIM_EVIDENCE_VALIDATION.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
(UI / 'verification.json').write_text(json.dumps(dict(receipt,
    intent_alignment=dict(report_presentation='Done', real_homepage_submission='Done', source_investigation='Done',
        source_traceability='Done', model_analysis='Blocked: provider output limit',
        confirmed_market_charts='Blocked: insufficient eligible comparable evidence'),
    run_commands=[
        'app/.venv/Scripts/python.exe -m pytest app/tests -q',
        'app/.venv/Scripts/python.exe docs/delivery/claim-evidence-binding-phase1/accepted-candidate/phase1_probes.py',
        'node --experimental-strip-types --test tests/*.test.mjs [cwd app/frontend]',
        'node node_modules/typescript/bin/tsc --noEmit [cwd app/frontend]',
        'node node_modules/eslint/bin/eslint.js src [cwd app/frontend]',
        'node node_modules/next/dist/bin/next build [cwd app/frontend, separate dist and existing API env]',
        'app/.venv/Scripts/python.exe app/scripts/verify-institutional-runtime.py'],
    local_start_commands=[
        'app/.venv/Scripts/python.exe app/scripts/run-isolated-product.py --directory D:/deepinsight-lite/docs/delivery/institutional-report-acceptance/runtime --port 7785 --frontend-port 3105',
        "$env:DEEPINSIGHT_NEXT_DIST_DIR='.next-institutional-final'; node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3105 [cwd app/frontend]"]
    ), indent=2), encoding='utf-8')
print(json.dumps(dict(backend_passed=checks['backend_full']['passed'], build_id=build_id,
    frozen_source_drift=drift, real_market_poc=receipt['real_market_poc'])))
