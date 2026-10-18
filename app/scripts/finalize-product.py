"""Create local delivery receipts from existing real records; no external calls."""
import hashlib,json,sqlite3,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_product.store import Store,now

APP=Path(__file__).resolve().parents[1];ROOT=APP.parent;OUT=APP/'data/product/evidence';DOCS=APP/'docs/product'
def write(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def main():
    store=Store(APP/'data/product');stamp=now();runs=[]
    for e in store.all('extractions'):
        runs.append(dict(kind='extract',id=e['id'],status=e['status'],run_id=e.get('run_id'),accounting=e.get('budget')))
    for j in store.all('jobs'):
        if j.get('kind') in ['ask','analysis'] and j.get('run_id'):
            runs.append(dict(kind=j['kind'],id=j['id'],status=j['status'],run_id=j['run_id'],accounting=j.get('metrics'),quality_status=j.get('quality_status')))
    config=json.loads((ROOT/'secrets/model.json').read_text(encoding='utf-8-sig'))
    incomplete=[r['id'] for r in runs if any(c.get('status')!='returned' for c in (r.get('accounting') or {}).get('calls',[]))]
    ledger=dict(recorded_at=stamp,endpoint=config['base_url'],requested_model=config['model'],underlying_model='Not independently verified',credential_present=bool(config['api_key']),
        sdk_retries=0,outer_retries=0,automatic_fallback=False,per_run_requests_limit=3,input_budget=60000,output_budget=8000,request_timeout_seconds=180,total_deadline_seconds=480,
        actual_requests=sum((r.get('accounting') or {}).get('requests',0) for r in runs),incomplete_usage_runs=incomplete,fee_receipt='Unavailable; N/A',runs=runs)
    write('model-call-ledger.json',ledger)
    anomalies=[dict(kind=r['kind'],record_id=r['id'],run_id=r['run_id'],call=c) for r in runs for c in (r.get('accounting') or {}).get('calls',[]) if c.get('output_tokens',0)>c.get('max_output',8000)]
    write('provider-usage-review-delivery.json',dict(recorded_at=stamp,status='REVIEW_REQUIRED',calls_exceeding_requested_caps=anomalies,fee_receipt='N/A',raw_usage_unchanged=True,automatic_retries=0))
    for file in ['market.sqlite3','agno.sqlite3']:
        origin=sqlite3.connect(store.root/file);backup=sqlite3.connect(OUT/('delivery-'+file))
        try:origin.backup(backup)
        finally:backup.close();origin.close()
    facts=store.all('facts');events=store.all('events');active=[f for f in facts if f.get('status')!='superseded'];meaningful=[e for e in events if e.get('kind')!='source_update' and e.get('status')!='superseded']
    write('SOURCE_REGISTRY.json',store.all('sources'))
    write('GOLDEN_FACTS_PENDING.json',dict(status='pending_review',facts=[f for f in active if f['id'].startswith('BNP-')]))
    write('final-counts.json',dict(recorded_at=stamp,registered_sources=len(store.all('sources')),source_health=dict(Counter(s.get('health') for s in store.all('sources'))),documents=len(store.all('documents')),
        active_candidate_facts=len(active),all_fact_versions=len(facts),human_approved=sum(f.get('human_review_status')=='approved' for f in active),active_events=len(meaningful),reports=len(store.all('reports')),actual_model_requests=ledger['actual_requests']))
    native=[j for j in store.all('jobs') if j.get('kind')=='analysis']
    for index,j in enumerate(reversed(native),1):write('ai-report-analysis-v'+str(index)+'.json',j)
    # Check credential values in shipped source/evidence, without printing them.
    paths=list((APP/'london_product').glob('*.py'))+list(DOCS.glob('*.md'))+list((APP/'frontend/src').rglob('*'))+list(OUT.glob('*'))
    leaks=[];checked=0;secret=config.get('api_key','').encode()
    for p in paths:
        if p.is_file():
            checked+=1
            if len(secret)>12 and secret in p.read_bytes():leaks.append(str(p.relative_to(ROOT)))
    write('secret-scan.json',dict(checked_files=checked,credential_body_matches=leaks,credential_values_printed=False))
    assert not leaks,'Credential content found in delivery output'
    test_text=(OUT/'python-tests-final.txt').read_text(encoding='utf-8-sig')
    test_summary=next(line for line in test_text.splitlines() if ' passed in ' in line)
    perf=json.loads((OUT/'performance.json').read_text(encoding='utf-8'))
    p95=lambda k:round(perf[k]['p95_ms'],2)
    report=f'''# London Office Market product technical test report

Recorded {stamp}. These are local engineering and execution results, not human approval of market facts.

## Fresh verification

- Python: **{test_summary}**, `app/data/product/evidence/python-tests-final.txt`.
- Python compileall and strict OpenSpec validation executed; their command results are recorded in the delivery transcript/verification receipts.
- Frontend production build, lint/type checks and 3/3 SSE tests passed. See `app/frontend/FRONTEND_VERIFICATION.md` and the 91-file `FRONTEND_BUILD_IDENTITY.json`. Latest build used the approved Linux mirror with identical authoritative source; upstream lock unchanged.
- Seven business pages and native `/chat` were exercised in the real browser. Evidence includes filters, quote/hash drawer, comparison refusal, reports/read/download, missing-channel feedback, settings save, jobs, real Chinese Agent answer and native session refresh recovery.
- Real source acquisition saved HTML/PDF/CSV/JSON, including the actual BNP PDF link followed from its saved page. Employment LF24 is explicitly May–July 2026 rolling average, not June-only or Q2.
- Independent review found and corrected budget lifetime/isolation, duplicate paid work, workflow skip-to-success, raw/normalized scale, conditional child retry and provenance defects. See `independent-review.md`; initial failed receipts remain preserved.

## Observed execution

Real extraction v2: 8 exact quotes from the original BNP Q1 report; two provider requests, 12,661 input/1,572 output tokens, 139.453s. Candidate facts remain needs_review where fields are unknown. Workflow Run `3e09d973-4511-4762-a241-e5385a2e4e10`; native extraction Run `2c7b503a-120a-4959-9053-d547be3df898`.

Async saved-evidence answer: two provider requests, 9,062 input/964 output tokens, first content6.673s, completion17.401s. Native Run `920cc028-85fb-4d86-9883-e5ddc352199a`. Browser Chinese answer and native reload use Run `7db1cd08-8be3-4700-b750-39ec97c1020a`.

Same-document extraction returned cached=true and zero new model requests in0.396s. Optional AI reports ran through native report workflow and separate analysis jobs. First analysis completed in59.8s, cached repeat in0.217s; its semantic problems are explicitly preserved. V2 concise analysis completed in approximately29.35s. It remains REVIEW_REQUIRED, with disclosed defects about combined pre-let/under-offer transaction area and an implied supply trend across unconfirmed publisher methods. No model response was made into approved source facts.

Total actual provider requests in this delivery: **{ledger['actual_requests']}**. One original streaming run has incomplete final usage; no zero substitution. Provider fee receipt unavailable: **N/A**. A provider output-cap/accounting anomaly remains disclosed in `provider-usage-review.json`. Post-response total-budget rejection is tested; it cannot undo provider billing.

## Performance and reliability

30 cached HTTP query samples: P95 **{p95('cached_http_facts')}ms**. 30 uncached direct SQLite/service reads: P95 **{p95('uncached_sql_facts')}ms** (not HTTP). 30 deterministic comparison/refusal requests: P95 **{p95('saved_deterministic_compare')}ms**. Three real PDF parse samples: median **{round(perf['pdf_parse']['p50_ms'],2)}ms**. The final sample arrays are retained in `performance.json`; model failures and network failures are retained in their original receipts. Dashboard browser commit timing is in `browser-performance-final.json`; local targets do not establish production SLA.

The original all-source batch had7 successes/4 failures and retained successes. Native Scheduler triggered real report generation while the browser was irrelevant; temporary minute schedule is disabled, and four product definitions remain. Generic scheduler history does not provide native report Run ID automatically; the corresponding report job stores the actual native Run ID.

Actual process restart preserved facts/reports/native sessions. A real BBC refresh was interrupted, recovered as interrupted, explicitly retried and reported its genuine network failure. A separate real subprocess was terminated between SQLite INSERT and COMMIT: uncommitted row absent and all existing facts unchanged. Loopback Apprise HTTP delivery plus successful-send dedup passed; no external recipient is configured or claimed.

Protected baseline:304 hashes checked unchanged, official UI tracked source unchanged at pinned commit. Credential-body scan writes counts and matches only, never the key. JSON exports and consistent SQLite backups are local evidence.

## Explicit unpassed gates

G0 annual-unit/method qualification, human fact approval, original four-report90% evaluation and three approved real market changes remain unpassed. Historical AC matrix is separately dated in `LEGACY_AC_STATUS.md` (24 PASS/5 BLOCKED/1 FAIL). These engineering tests do not rewrite it. AI semantics remain review-required. External notification delivery and public deployment are not verified.
'''
    (DOCS/'B1_TEST_REPORT.md').write_text(report,encoding='utf-8')
    acceptance=f'''# London Office Market product acceptance

Recorded {stamp}. **Local product is running and its technical business flows have real evidence. Overall acceptance: PARTIAL.** Human data approval, AI semantic review and configured external delivery remain separate gates.

| Area | Status | Actual result / evidence |
|---|---|---|
| Frozen baseline | PASS | Agno2.9.0, official UI SHA6dad9593, independent business copy;304 protected hashes unchanged |
| F1 acquisition | PASS capability / PARTIAL coverage | 13 sources, real HTML/PDF/CSV/JSON, hashing and provenance; official source failures/restriction visible; not exhaustive industry news |
| F2 extract/governance | PASS execution / PARTIAL approval | 8 raw model candidates matched exact saved quotes; raw/normalized fields separate; {len(active)} active candidates, zero human approval; annual rents unresolved |
| F3 history/compare | PASS rules / BLOCKED formal market deltas | Atomic SQLite, identities and history; three actual core pairs return not_comparable with reasons; positive arithmetic is constructed rule testing only |
| F4 monitor/events | PASS local execution | {len(meaningful)} distinct active real article events; bounded discovery, event versions, thresholds,4 native schedules, visible source failures, explicit retry |
| F5 Agent Q&A | PASS execution / REVIEW_REQUIRED semantics | Real Agent+Tools streaming and native history after restart; facts/citations/periods shown; raw model answers are not approved facts |
| F6 reports | PASS execution / PARTIAL quality | HTML/Markdown export/download; native report workflow; explicit background AI draft/caching; known draft quality issue disclosed, raw output retained |
| External notifications | BLOCKED | No configured external destination; configuration_missing returned. Real loopback transport/dedup verified, no external-send claim |
| Seven product pages | PASS | Overview, data, events, ask, reports, settings and jobs exercised; native chat retained |
| Performance | PASS local deterministic targets | Cached HTTP and deterministic compare targets met in measured samples; model latency and slow source failures retained |
| Recovery/idempotence | PASS tested boundaries | Real restart, interrupted collection, killed uncommitted DB transaction, duplicate import/extraction and successful retry cache |
| Safety/config | PASS local boundary | Loopback/Origin checks, public-source allowlist/IP pinning, parser guards, server-only credential, escaped reports, no autonomous external sends |
| Deployment | PARTIAL | Working local Windows/WSL product; public TLS/auth/service installation and clean-machine reinstall not claimed |

## Important evidence

- `app/data/product/evidence/result-package.json`: actual source/document/fact/comparison/event/job/model/report records, including failure and historical versions.
- `SOURCE_REGISTRY.json`, `original-hashes.json`, `GOLDEN_FACTS_PENDING.json`, `final-counts.json`: local review indices.
- `real-extraction-v2.json`, `model-call-ledger.json`, `ai-report-v2-result.json`, `ai-semantic-review-v1.json`, `ai-semantic-review-v2.json`, `provider-usage-review.json`: actual outputs, corrections, unknowns and budgets.
- `browser-*.txt/png/json`, `performance.json`, `write-interruption.json`, `interrupted-job-*.json`, `cached-extraction-result.json`, `scheduler-workflow-result.json`, `independent-review.md`: runtime/browser/recovery/review evidence.
- `delivery-market.sqlite3` and `delivery-agno.sqlite3`: consistent delivery backups; active databases remain under `app/data/product`.

## Remaining decisions and limitations

1. Review the six core facts in `B1_HUMAN_REVIEW_CHECKLIST.md`. None is approved on the user's behalf. No annual rent inference or forced vacancy-method alignment was introduced.
2. Original AC26 remains FAIL and G0 remains BLOCKED. `LEGACY_AC_STATUS.md` lists all30 historical outcomes and the newer scope override without retroactive success.
3. AI v1 made incorrect coverage/count statements. V2 removed these patterns but overstates pre-let area and implies supply contraction across unconfirmed cross-publisher inputs. These are known semantic defects, not approved conclusions. Reports disclose issues; historical snapshots containing subsequently superseded records are labelled superseded. Source observations and original report bytes remain unchanged. A fresh deterministic weekly report uses current records without additional model requests. No further model repair retry is automatic.
4. Provider reported two analysis calls above requested per-call max_tokens=1,800 (7,268 and3,123 output tokens); both run totals stayed below8,000. Usage/cap semantics and fees are not independently verified. See provider-usage-review-delivery.json. Total-budget overrun responses are rejected; billing cannot be reversed by a local guard.
5. CBRE, Planning Datahub, Savills live URL and BBC RSS encountered real access/network failures; original saved Savills PDF remains usable. Knight Frank AI use is disabled. BNP next-quarter landing rollover still requires catalog maintenance. ESG/hybrid themes and planning dataset completeness are not asserted from absent evidence.
6. No external notification destination is configured. Do not treat local loopback delivery as email/Slack delivery.
7. The authoritative frontend's Windows-mount dependency link intermittently disappeared; the cause is unproven. Matching Linux-mirror production build passed, pinned lock/source hashes retained, and guarded build helper/check is documented. Local launch verified; public production readiness is not claimed.

## Operate

Open **http://127.0.0.1:3101**. Start/stop via `app/Start-London-Market.cmd` and `app/Stop-London-Market.cmd`, or the commands in `B1_RUNBOOK.md`. Native AgentOS is127.0.0.1:7780; old B0/B1 services and Radar were not modified. The repository root has no Git metadata, so whole-project commit is N/A; delivery file hashes provide the local change identity. No PPT was produced and no unrequested next-phase work is started after this delivery.
'''
    (DOCS/'B1_ACCEPTANCE_REPORT.md').write_text(acceptance,encoding='utf-8')
    files=list((APP/'london_product').glob('*.py'))+list((APP/'product_skills').rglob('SKILL.md'))+list((APP/'tests').glob('test_product*.py'))+list(DOCS.glob('*.md'))+list((APP/'scripts').glob('*product*'))
    files += [APP/p for p in ['README.md','requirements-product.lock.txt','.env.product.example','Start-London-Market.cmd','Stop-London-Market.cmd','migrations/002_product.sql','PRODUCT_EXECUTION.md','PRODUCT_API_CONTRACT.md','frontend/package.json','frontend/pnpm-lock.yaml','frontend/FRONTEND_BUILD_IDENTITY.json','frontend/build-product.sh','frontend/PRODUCT_FRONTEND.md','frontend/FRONTEND_VERIFICATION.md']]
    write('DELIVERY_MANIFEST.json',dict(recorded_at=stamp,git_commit='N/A; project root has no Git repository',files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}))
    print(json.dumps(dict(recorded_at=stamp,active_candidates=len(active),active_events=len(meaningful),model_requests=ledger['actual_requests'],incomplete_usage_runs=len(incomplete),credential_body_matches=len(leaks),test_summary=test_summary)))


if __name__=='__main__':main()
