# DeepInsight Lite Railway deployment acceptance (2026-10-19)

This report records the **Lite** deployment only. The separate Mini project was not edited by this deployment session. A successful HTTP status is not counted as proof of market-analysis quality.

## Deployment identity and access

- Workspace: `Benjamin Daoson's Projects` (`6ab97376-3512-44cc-96bb-a8cd953386cf`), observed Railway plan: **Trial**.
- Lite project: `deepinsight-lite` (`68317bb1-cfa9-4756-94b9-393f834d8e34`), environment `production`.
- Public frontend: <https://lite-frontend-production.up.railway.app/>. The site requires HTTP Basic authentication (`reviewer`). The generated password is in the local, untracked file `D:\deepinsight-lite-railway-release-20261019\access-secret.txt`; it is not in this repository or the image.
- `lite-frontend` service `49c29fe6-9f64-4312-b5be-36161d8d920d`, successful deployment `109b4a61-1cf1-44fb-8b06-502597766083`.
- `lite-backend` service `445a4fae-ce02-4978-ab86-3ce9c63b3e0c`, successful deployment `66bc33a9-f1c5-4dac-9fd3-4048303cd838`. No public backend domain; frontend proxies to `lite-backend.railway.internal:8080`.
- Backend volume `lite-backend-volume` (`3c687233-589d-4dec-99e5-3287cfaed1c1`) mounted at `/persist`, separate from Mini.
- Source baseline HEAD `6d00b43b9086965e3af637ae321b1ee16d2d8c20` **plus uncommitted product files**. A frozen local upload snapshot was deployed; its 505-file SHA-256 manifest digest is `c12a47a1d0ae2b12ca95b7e21a3239578537f08e0bd0bdfbc2ee684a70df76da`. Manifest: `D:\deepinsight-lite-railway-release-20261019\acceptance\release-manifest.json`. Do not present HEAD alone as the deployed version.

## Observed acceptance

| Check | Status | Actual observation |
| --- | --- | --- |
| Backend and frontend deployment | PASS | Both services have a successful deployment and one running replica. Backend log shows one Agno scheduler poller and Uvicorn on `0.0.0.0:8080`. Authenticated public `/health` reports `ok`, `live`, version `2026.10.19`. |
| Frontend to private backend | PASS | Authenticated public `/api/market/overview` returned saved market data. Backend has no public domain. |
| Page routes over HTTPS | PARTIAL | Authenticated HTTP GET returned 200 for `/`, `/ask`, `/chat`, `/overview`, `/market-data`, `/events`, `/reports`, `/settings`, `/jobs`. Browser automation could not pass the site's HTTP Basic challenge (`ERR_INVALID_AUTH_CREDENTIALS`), so JS behavior, navigation, and visual quality were not verified in the public browser. Evidence: `D:\deepinsight-lite-railway-release-20261019\acceptance\page-http-check.json`. |
| Real AI question | BLOCKED | One Native Agent public SSE request reached the configured relay and failed with `PROVIDER_QUOTA_EXHAUSTED`. Run `69602b77-04a3-47d6-8f9f-d8766ad26961`; submission `3d6977ac-996e-43fc-a41b-2eed25c1de36`. One provider request, input estimate 11,573 tokens, output cap 1,800; **actual** tokens and fee unavailable (`N/A`). The error was surfaced, with no automatic retry or provider switch. Configured model `claude-sonnet-4-6` via the existing OpenAI-compatible relay; upstream model identity was not independently verified. No successful AI analysis is claimed. Raw SSE: `D:\deepinsight-lite-railway-release-20261019\acceptance\test2.sse`. |
| Continuous AI conversation | BLOCKED | The first model call exhausted provider quota; the requested follow-up was not sent. Context carryover in the cloud was not proven. |
| Source-backed report | PARTIAL | A deterministic weekly report was generated and persisted, ID `20613056-1e03-4d53-a4cf-ded54a261558`, Agno workflow run `190588f0-1a87-49f4-8b8f-82a5d23a7038`. It contains 60 fact IDs, 30 event IDs, review labels, 95 URL occurrences, and 46,780 Markdown characters. Public Markdown and HTML downloads succeeded and survived redeployment. Requested **AI-generated** briefing was not run after quota failure. Evidence: `D:\deepinsight-lite-railway-release-20261019\acceptance\weekly-report.md` and `.html`. |
| Real monitoring | PARTIAL | Manual cloud refresh job `8c18dba8-13da-459e-bcc4-cf2ae53547ef`, Agno run `3273277b-70dd-4d57-98ef-b82b0bf8bcb4`, completed `partial`: 14 sources saved, 2 unchanged, 3 failed (Savills/City of London ConnectError; CBRE HTTP 403). No invented alert; 23 observations/comparisons were withheld as invalid or not comparable. News job `75f2734b-28f2-4edc-8f92-be57e12dec58` reused one bounded Tavily discovery receipt (1 credit, zero qualifying candidates) and had one source failure. Evidence: `D:\deepinsight-lite-railway-release-20261019\acceptance\monitor-result.json`, `news-monitor-result.json`. Browser Monitoring action was not verified. |
| Scheduler | PARTIAL | Four persisted Agno plans are enabled, now all `Europe/London`. A focused local regression passed 7/7. Cloud log shows one poller. Manual jobs ran; a future clock-triggered occurrence has not yet been observed on this deployment. |
| Evidence integrity | PASS | A cloud document download (`0ba7977f-b082-4463-9bac-0afa862c87bc`) returned 200, 30,883 bytes, and matched its stored SHA-256 `5213193de6ac838734949d77d828f5526b7dfc9a2a9ebcaac561d3cbecc47388`. The deployment preparation verified 108/108 retained original source hashes. |
| Persistence | PASS | Following Lite backend restart and redeployment, the same report (46,780 Markdown characters) and monitoring job remained accessible; `/persist` held the SQLite databases and evidence. `df -h /persist` reported 47 MB used of 434 MB mounted. |
| English-only UI and report | PARTIAL | The checked rendered route HTML and generated report use English, but full interactive browser content and every error state were not observed. |
| Notifications | BLOCKED | No destination is configured. The API truthfully reports `configuration_missing`, `external_delivery_verified=false`; no external message was sent. |
| Mini isolation | PASS | Mini remained in its separate project `7d5ba219-cc57-440f-a974-e884ab4c7179`, service `deepinsight-mini-web` (`61a6dacb-9f2c-47ce-8752-3e3b0e89de8e`). <https://deepinsight-mini-web-production.up.railway.app/health> returned `ok`, product `London Office Intelligence`, scheduler `independent`. This session issued no Mini write/restart/delete command. |

## Resource and release notes

- Railway `metrics --all --since 1h` near acceptance: Lite backend memory 170.6 MB, frontend 186.2 MB; each had a 1 GB Trial service limit. CLI volume metric reported 0.69 MB, while the container filesystem reported 47 MB used; use the filesystem observation for actual stored data and treat the metric discrepancy as unresolved.
- Workspace `railway usage --json` recorded approximately `$0.00376` current usage at the end of testing, across the workspace, without a configured usage hard limit. This is a point-in-time reading, not a forecast or a Lite-only bill. Trial credit and duration are finite. No plan upgrade or purchase was made.
- `railway usage projects --project deepinsight-lite --json` separately recorded approximately `$0.00138` of that current usage for Lite (`$0.00072` backend, `$0.00066` frontend); these metered amounts continue to change while services run.
- The uploaded 505 files were scanned against the exact current local model key, Tavily key, and site password: zero matches. Secrets were supplied as Railway service variables, not baked into images or this report.
- Frontend production build, lint and TypeScript checks passed; 39 frontend tests passed. Focused Python API/monitor/news tests passed 23/23 before deployment, and scheduler timezone regression passed 7/7 afterward. These are code checks and do not replace browser or model quality acceptance.
- This release is **not yet suitable as a fully verified AI demonstration**. The public URL is live and saved market-data/report/monitoring paths work, but the model relay needs restored quota and the protected browser flow needs human verification before recruiter-facing use.

## Reproduction and operations

Local snapshot preparation: `python deploy/railway/prepare_snapshot.py` (inspect its explicit paths and allowlist first). The uploaded backend and frontend contexts are in `D:\deepinsight-lite-railway-release-20261019\backend-upload` and `frontend-build`. Re-deploy each context from its own working directory using `railway up --project 68317bb1-cfa9-4756-94b9-393f834d8e34 --environment production --service <exact Lite service ID> --detach --yes`. Do not deploy the repository root to both services. Do not log Railway variables in KV/JSON form.

Read-only checks:

```powershell
railway deployment list --project 68317bb1-cfa9-4756-94b9-393f834d8e34 --environment production --service 445a4fae-ce02-4978-ab86-3ce9c63b3e0c --limit 1 --json
railway deployment list --project 68317bb1-cfa9-4756-94b9-393f834d8e34 --environment production --service 49c29fe6-9f64-4312-b5be-36161d8d920d --limit 1 --json
railway usage --json
```

The public site can be opened at the URL above with username `reviewer` and the locally saved password. Restoring model service quota and supplying an authorized notification destination are external prerequisites; do not silently switch models or claim notifications were delivered.
