# London Office Market product acceptance

Recorded 2026-10-18T00:05:24.322506+00:00. **Local product is running and its technical business flows have real evidence. Overall acceptance: PARTIAL.** Human data approval, AI semantic review and configured external delivery remain separate gates.

| Area | Status | Actual result / evidence |
|---|---|---|
| Frozen baseline | PASS | Agno2.9.0, official UI SHA6dad9593, independent business copy;304 protected hashes unchanged |
| F1 acquisition | PASS capability / PARTIAL coverage | 13 sources, real HTML/PDF/CSV/JSON, hashing and provenance; official source failures/restriction visible; not exhaustive industry news |
| F2 extract/governance | PASS execution / PARTIAL approval | 8 raw model candidates matched exact saved quotes; raw/normalized fields separate; 32 active candidates, zero human approval; annual rents unresolved |
| F3 history/compare | PASS rules / BLOCKED formal market deltas | Atomic SQLite, identities and history; three actual core pairs return not_comparable with reasons; positive arithmetic is constructed rule testing only |
| F4 monitor/events | PASS local execution | 6 distinct active real article events; bounded discovery, event versions, thresholds,4 native schedules, visible source failures, explicit retry |
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
