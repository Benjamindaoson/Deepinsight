# London Office Market product runbook

## Structured official feeds and fast saved-data routing — 2026-10-18

The existing `MarketService` / Agno Workflow now reads four bounded, read-only Planning London Datahub application searches (City of London, Westminster, Tower Hamlets and Camden) and the official Nomis BRES London workplace-employment CSV. All are registered sources, fetched in the existing four-request concurrent acquisition path, stored as immutable originals with URL/SHA-256 and source health, and projected into **pending-review** candidate events or annual workplace-employment observations. A planning application is never treated as completed supply; the latest currently returned BRES years are 2023 and 2024, and all-industry jobs are not an office-occupier demand estimate. The original GLA landing source remains historically preserved and is disabled only at its known obsolete URL. The official non-domestic EPC source is registered but remains `configuration_missing` until a government bearer token is separately configured; no unauthenticated request is attempted. Its property-level records cannot establish an office-market ESG trend.

The `/ask` page defaults to Auto: bounded saved-data lookups use local deterministic evidence retrieval and zero model calls; risks, opportunities, causes and trend interpretations retain the existing native Agent, budget and publication gates. External source fetches run in background jobs and never block a question. The `/` native Agno chat still uses its existing model and sessions; a complete AI analysis is **not** covered by the two-second saved-data target. On 2026-10-18, one real market refresh returned `partial` with 14 successful or unchanged sources and two HTTP 403 failures (CBRE, Savills), while all five new official API sources succeeded. Agno Run `a7b5f661-8682-4399-a7c4-6baadd25d51d` and its documents/facts/events are recorded in `app/data/product/evidence/structured-signals-routing-20261018/`. Thirty local saved-route requests gave p95 completion 138.5 ms with zero model requests; this is a loopback observation, not a production SLA or a measured AI answer time. No new Tavily, model or external notification call was made for this refresh or benchmark.

After the final integration regression, `GBP/sqft` without an explicit time denominator remains an unresolved rent quotation; no annual normalized value is produced, and a reviewer note alone cannot approve an annual basis inferred by convention. A model draft with an unverified trend stays withheld even if another candidate series exists. These fail-closed behaviors and the evidence-pack variable-shadowing repair passed the full **230-test** backend suite. The real browser `/ask` saved-data query remained functional after restarting the current backend; the current round did not perform a new paid AI semantic acceptance. One detached backend launch exited without an application traceback during this run; a foreground launch restored the browser query, and the reason for the earlier exit remains unresolved. Full results and remaining limits are in `app/data/product/evidence/structured-signals-routing-20261018/ACCEPTANCE_REPORT.md`.

For this workstation, numeric-IP DNS-over-HTTPS was unreachable through its TUN. The fetch guard now resolves through HTTPS-verified `cloudflare-dns.com`, still rejects non-public answers and pins publisher connections to the resolved public IP. No redirect, domain or HTTP policy was relaxed. Optional EPC setup uses only `LONDON_EPC_TOKEN` in the backend process environment; obtain it through the official government access process and never place it in frontend configuration or logs. After configuring it, restart the backend and explicitly verify the live schema before treating that feed as active. The existing runbook sections below describe the other original sources and jobs.

## News discovery and notification supplement — 2026-10-18

The existing `london-news` Workflow now optionally discovers up to five candidate URLs with Tavily before acquiring their originals through the existing source transport. No new schedule, database, model call, event engine or notification transport is introduced. The other three schedules are unchanged. The legacy disabled `product-verification-once` schedule remains preserved.

Tavily is **disabled by default**. The inherited `TAVILY_API_KEY` is deliberately ignored. The owner must provision a **new** dedicated `LONDON_TAVILY_API_KEY` locally and explicitly set `LONDON_TAVILY_ENABLED=1` after authorizing search usage. Never paste a key into chat, a command literal, a report, Git or `NEXT_PUBLIC_*`. `app/.env.product.example` is documentation, not an auto-loaded secret file.

For a local interactive PowerShell session, read credentials without echoing them; they are inherited only by a backend started from that session:

```powershell
# Owner-only setup; do not run during unapproved tests.
$discoverySecret = Read-Host 'NEW dedicated Tavily key' -AsSecureString
$env:LONDON_TAVILY_API_KEY = [System.Net.NetworkCredential]::new('', $discoverySecret).Password
Remove-Variable discoverySecret
$env:LONDON_TAVILY_ENABLED = '1' # Explicit opt-in to scheduled search usage
# Separately, only for an approved notification recipient/channel:
$notificationSecret = Read-Host 'Approved Apprise destination URL' -AsSecureString
$env:LONDON_NOTIFICATION_URL = [System.Net.NetworkCredential]::new('', $notificationSecret).Password
Remove-Variable notificationSecret
# Restart only when no collection/extraction/analysis job is running.
& app/scripts/product-stop.ps1
& app/scripts/product-start.ps1
```

`GET /api/market/settings` exposes only redacted discovery readiness. Search uses fixed `https://api.tavily.com/search`, `topic=news`, `search_depth=basic`, `max_results=5`, `include_answer=false`, `include_raw_content=false`, `auto_parameters=false`, and enabled approved domains. No SDK/fallback/retry is used. It makes at most one attempt in each UTC-aligned six-hour window, including failed attempts; the actual provider request ID and returned credit usage, if available, are saved. Window-boundary calls can occur less than six hours apart. Search charges cannot be inferred from token budgets; no monetary billing verification has been performed.

Search claims/receipts/candidates live in existing `jobs` records (`kind=news_discovery`); original snapshots remain in `documents`/`artifacts`, and extracted reported events remain in `events`. Search snippets, titles and publication dates are not imported as facts. The original supplies the evidence and available publication metadata; missing dates remain null. Original acquisition uses registered HTTPS hosts, same-publisher redirects, public-IP-pinned sockets, bounded redirects/time/bytes and existing parsers. Knight Frank remains excluded. Inaccessible originals remain `needs_review` candidates in the receipt, with no event inferred from the snippet. Successful original extraction remains `pending_review`, never approved.

Ordinary news schedules call the adapter; individual-source retries and market refreshes do not invoke Tavily. Search failures are cached within the window; explicit source recovery can reuse saved candidates without another search request. A receipt interrupted during search blocks resubmission in that window because the paid outcome is unknown. Candidate originals use the existing four-request concurrency bound; cached originals are hash checked. The existing Job Status Audit details show the discovery receipt and candidate outcomes. `configuration_missing`/`disabled` skip discovery while ordinary registered-source acquisition continues.

Notification syntax preflight is safe and read-only:

```powershell
& app/.venv/Scripts/python.exe app/scripts/notification-check.py
```

It calls `GET /api/market/notifications/configuration`, reports `configuration_missing`, `configuration_invalid` or `configured`, and does **not** establish a connection or send. `configured` is not proof of delivery. After a recipient and report are explicitly authorized, enable notifications in the existing Monitoring page, then use the existing Reports send action or:

```powershell
& app/.venv/Scripts/python.exe app/scripts/notification-check.py --send-report APPROVED_REPORT_ID --confirm-external-send
```

This reuses `POST /api/market/notifications`, the report lock, sent-record dedup and persisted notification history. Configuration exceptions become sanitized failures. Exceptions after send dispatch become `delivery_unknown` and cannot be automatically retried; inspect the channel before resolving ambiguity. A successful Apprise boolean is recorded as `apprise_transport_acceptance`, not recipient delivery confirmation. Report schedules retain zero automatic notification retries. Missing destination returns `configuration_missing`; disabling notification in settings returns `disabled`.

Live state updated 2026-10-18: the owner-authorized new Tavily key is configured and discovery is ready. One real API search succeeded (1 provider credit); MCP initialization and tool listing also succeeded. No notification destination is configured and notifications remain disabled. Four business schedule IDs are unchanged. External recipient delivery remains BLOCKED on destination/authorization. The full offline-fixture chain and real localhost HTTP notification are explicitly distinguished from external acceptance in `app/data/product/evidence/news-discovery-notifications-20261018/ACCEPTANCE_REPORT.md`.

2026-10-18. Current product phase is authorized independently of historical B1-G0 qualification. The old B0 framework validation, old B1 results and Radar/A route remain separate. No PPT is included.

## Open and operate

Open **http://127.0.0.1:3101**. Double-click `D:\deepinsight-lite\app\Start-London-Market.cmd` to start the installed local product; double-click `Stop-London-Market.cmd` to stop its two verified services. Normal collection, filtering, evidence review, questions, reports, notifications and settings use the web pages.

Use Market Data to inspect the source-native values and periods. View evidence opens the saved quote, page, hash and original file. Extract this document explicitly starts bounded real model processing; collection and saved queries do not do this automatically. Changes & Events compares selected facts, and returns specific refusal reasons for pending or incompatible records. Reports generates deterministic daily/weekly evidence summaries. Generate AI weekly (model) explicitly submits a background native report workflow; successful analysis is cached against saved evidence, kept separate from facts, and remains REVIEW_REQUIRED. Known interpretation errors are disclosed on the report, and original failed/superseded drafts remain available. Ask Market Agent provides native model answers with source citations and review boundaries. Native chat and durable sessions remain at `/chat`.

## Verified environment and installation

- Windows Python **3.12.10**, independent `app/.venv`, Agno **2.9.0** and SQLAlchemy **2.1.5**. Exact installed Python dependencies: `app/requirements-product.lock.txt`. Original B1 lock remains unchanged.
- Business UI is an independent archive of official Agent UI commit **6dad9593fca6756e1813e4f4b3b2620be6377691**. Its frozen pnpm lock remains the original blob **6902c0b9d1b5c8d65b3e15f33526388b0a744b64**. No upstream source is edited.
- Previously verified WSL Node **24.18.0**, pnpm **10.34.5** with a separate Linux dependency store. This round used Node **24.16.0**, pnpm **11.15.1** and a project-local `app/frontend/node_modules` install from the unchanged frozen lock. `app/frontend/pnpm-workspace.yaml` carries the existing picomatch override and explicitly permits the official `sharp` install script. Turbopack build, typecheck, lint and 25 frontend tests passed. The build helper accepts either the previous approved link or this project-local directory.

The exact environment install/restore commands (from the project root) are:

```powershell
py -3.12 -m venv app/.venv
uv pip sync --python app/.venv/Scripts/python.exe app/requirements-product.lock.txt
```

The existing environment was used and the three added dependencies were installed with `uv pip install --python app/.venv/Scripts/python.exe Jinja2==3.1.6 apprise==1.9.8 openpyxl==3.1.5`. The full fresh-environment restore above is documented, not claimed as a second clean-machine installation test.

```bash
# WSL, exact install and build commands used
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/app/frontend
npm exec --yes --package=pnpm@10.34.5 -- pnpm install --offline --frozen-lockfile --package-import-method=copy --virtual-store-dir /home/benjamin/.cache/deepinsight-product-frontend/node_modules/.pnpm
npm exec --yes --package=pnpm@10.34.5 -- pnpm build
npm exec --yes --package=pnpm@10.34.5 -- pnpm typecheck
node --experimental-strip-types --test tests/*.test.mjs
```

## Start, test and stop

The final production bundle was built from an identical Linux source mirror after Windows-mount EACCES errors. The guarded reproduction helper is `app/frontend/build-product.sh`: `wsl.exe bash /mnt/d/deepinsight-lite/app/frontend/build-product.sh --check` passed against the installed environment. To rebuild, first stop only the product UI, then use the same command with `--build`, and restart it. The helper's syntax, help, read-only check and full `--build` wrapper all passed. The final report-table fix was built through this wrapper, including Next production lint/type validation, standalone typecheck and all three SSE tests; the exact product UI launcher then restarted it. See `app/frontend/PRODUCT_FRONTEND.md` and `FRONTEND_VERIFICATION.md` for the exact build evidence and identity.

These commands were executed in this workspace:

```powershell
# D:\deepinsight-lite
& app/scripts/product-start.ps1
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh
# Runtime 127.0.0.1:7780; UI 127.0.0.1:3101
& app/scripts/product-launch.ps1 -NoBrowser

# D:\deepinsight-lite\app
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m compileall -q london_product
.venv/Scripts/python.exe scripts/verify-product.py
openspec validate london-market-product --strict

# D:\deepinsight-lite
& app/scripts/product-stop.ps1
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh
```

The UI shell command is foreground when run directly; the double-click launcher runs it hidden. The Python stop script verifies the listening process is the product runtime. The UI stop script matches its exact working directory and Next process. Neither touches B0/B1 ports 7777/7778/3100 or any other project.

`verify-product.py` makes only local saved-data API/SQLite requests; it does not call a model or external source. It performs measured reads, deterministic comparisons, a real subprocess kill before SQLite commit, protected-file hash checks and result exports. Its transaction probe runs with an uncommitted job row and confirms rollback; no fabricated market fact is committed.

## Data, native runtime and recovery

Business DB: `app/data/product/market.sqlite3`; native AgentOS sessions/runs/traces/schedules: `app/data/product/agno.sqlite3`. Migration: `app/migrations/002_product.sql`. Originals: `app/data/product/originals` and `artifacts`; evidence and receipts: `app/data/product/evidence`.

SQLite WAL and atomic transactions protect writes. A stopped process rolls back incomplete writes. On startup queued/running jobs and extraction attempts become interrupted, visible for explicit retry. Failed/interrupted/partial collection and extraction jobs can be retried from Job Status. Failed questions or reports link to their own page for explicit resubmission; model calls are never silently replayed. A successful same-document/same-version extraction is reused with zero model requests. Sources are fetched concurrently (maximum four); jobs use two workers. Unrelated source failures produce partial results, not discarded successes.

Four persistent native Scheduler definitions are created/upserted without duplicates: news every six hours, market weekly, daily report at 08:00 UTC, weekly report Monday 08:00 UTC. Settings shows actual cron/timezone. Supported exact cadences are 1/2/3/4/6/8/12/24/168 hours. Thresholds default to rent 5%, take-up 10%, vacancy 0.5 pp and apply only to compatible reviewed facts within selected monitoring scope. Quarterly collection and news polling make no implicit model extraction calls. Scheduling requires the Python service to remain running; browser closure has no effect. Windows login autostart or a remote service installation is not included.

## Persistent Tavily configuration (verified 2026-10-18)

`product-start.ps1` loads project-local `secrets/tavily.json` via `load-tavily-config.ps1`. Its shape is `{"api_key":"YOUR_NEW_KEY","enabled":true}`; the local file takes precedence over stale process variables. Both credential files have current-user-only Windows ACLs and Git ignore rules. Never copy actual values into logs or frontend files.

Project `.codex/config.toml` registers `tavily_london` as Streamable HTTP at `https://mcp.tavily.com/mcp/`, authenticating via a header, with only `tavily_search` exposed. CLI configuration loading and a real MCP handshake/tools-list were verified. An already-open Codex conversation may need a new session or MCP reload to refresh its tool list; the current conversation did not issue a MCP search. Do not equate configuration with current-session hot loading.

Both configurations default to fast search and five results, without generated answers/raw-content expansion. Product discovery additionally enforces the durable one-search-per-six-hour gate, exact publisher allowlist, redirect/IP protection and original-document verification. The MCP defaults are convenience settings, not this product's persistence/authorization guard: future interactive calls must apply the approved domain list, avoid unapproved Knight Frank content, and never treat snippets as verified facts. MCP searches are separate API usage and are not counted by the product six-hour receipt.

Observed product search: 8.088 seconds, 1 credit, one JLL URL; full existing news Workflow: 33.511 seconds, PARTIAL because Planning returned HTTP 403. The discovered original matched an existing Q3 2026 JLL snapshot and retained pending_review. This is a connectivity/ingestion success, not proof of fresh-news recall, exhaustive thematic coverage or a latency SLA. See `app/data/product/evidence/tavily-live-setup-20261018/ACCEPTANCE_REPORT.md`.

## Model and notification configuration

The server reads the existing authorized `secrets/model.json`; it was not changed. Actual endpoint/model and non-secret bounds are recorded in `evidence/model-call-ledger.json`. SDK, Agno and outer automatic model retries are zero; there is no fallback model. Each operation has at most three model requests, 60,000 input-token reserve, 8,000 output-token reserve, 180 seconds per request and 480 seconds total. UTF-8 byte estimates conservatively reserve context before requests; reported totals above budget are rejected after response and before publication. The provider reported two analysis calls above requested per-call max_tokens=1,800: 7,268 and 3,123 output tokens (run totals7,383 and3,243, both below8,000). These anomalies are retained in `provider-usage-review.json` and the complete `provider-usage-review-delivery.json`. Server-side guards cannot undo already incurred provider billing or prove the provider honors per-call cap semantics. Monetary cost is N/A where the provider gives no fee receipt; underlying model identity and usage remain provider claims. Retrieval context is bounded and ordinary answers use one Agent with Tools.

Set **server process environment** `LONDON_NOTIFICATION_URL` to a valid Apprise destination, then restart the runtime and enable notifications in Monitor Settings. Do not place it in frontend environment, source URLs, browser forms, exported records or Git. `.env.product.example` is an example only; it is not automatically loaded. Delivery without configuration returns `configuration_missing` and sends nothing. Explicit send and scheduled sends persist success/failure receipts; retry a failed delivery from Reports, while successful report deliveries are deduplicated. No external destination is configured in this delivery. A genuine loopback HTTP Apprise test verifies the transport, not an external recipient.

## Source and safety boundaries

Only registered public HTTPS destinations are fetchable. Public DNS/IP checks, pinned transport, redirect guards, byte/page/segment/connection timeouts and parser guards reject private, loopback, file and off-list targets. The local machine's synthetic DNS ranges have a narrowly scoped authenticated public DNS fallback; private addresses remain rejected. Raw document text is untrusted input, never an instruction source. Native model tools are restricted to read-only saved-data retrieval and deterministic comparisons. Model output never approves facts or changes comparison rules.

The server binds loopback and checks Host plus mutation Origin; CORS permits the business UI only. This is a local single-user deployment. Public exposure, TLS, reverse-proxy authentication, multi-user authorization, encrypted backups and tenant isolation require a separate deployment review. Browser pages and report exports escape untrusted text; copied native image fallback no longer uses HTML interpolation.

Knight Frank is disabled and prohibited from AI processing due to its explicit document restriction. Saved authorized BNP/JLL/Savills originals are reused. CBRE, Planning London Datahub and BBC RSS failures are visible; other sources continue. BNP's current catalog landing page is Q2 2026; moving to a later report requires catalog maintenance. Public article discovery is bounded to observed publisher pages and two actual links; it does not claim exhaustive news coverage.

Unknown annual rent units, source methods and human review remain unresolved. No formal three-pair market change, original 90% evaluation pass or investment conclusion is claimed. See `B1_HUMAN_REVIEW_CHECKLIST.md`, `LEGACY_AC_STATUS.md` and `B1_ACCEPTANCE_REPORT.md` for the evidence boundary.
