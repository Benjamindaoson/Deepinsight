# G0 — frontend audit and baseline

Date: 2026-10-18. Result: **PASS for runnable baseline; known UX defects retained for repair.**

Identity: D:/deepinsight-lite, independent application app/frontend + app/london_product. This is not the sibling D:/deepinsight-rader. Source is an archived working copy with no .git; 94 source/test/config files backed up in evidence/before-source.zip with SHA-256 manifest. No business data, provider secrets, model configuration or schedules changed.

Stack: Next.js 15.5.18, React 18.3.1, TypeScript, Tailwind, Radix, Zustand and nuqs; pnpm-lock.yaml retained. Frozen WSL Node 24.18.0 and independent dependency directory verified by build-product.sh --check. Windows FastAPI/Agno backend at 7780 uses app/.venv. Frontend production server at 3101. build-product.sh performs an isolated source-mirror production build; product-ui-start.sh serves it. Commands: node --experimental-strip-types --test tests/*.test.mjs; node_modules/.bin/eslint src; node_modules/.bin/tsc --noEmit; build-product.sh --build. No dependency install is needed.

Nine real HTTP routes return 200: /, /chat, /overview, /market-data, /events, /ask, /reports, /settings, /jobs. Existing tests 9/9 pass. Real browser home, overview, monitoring and saved conversation restored; preceding review also walked evidence/events/reports/jobs. Baseline screenshots in evidence/before. API snapshots include overview/settings/jobs/reports/facts/sources. Direct native history GET sampled 200, 45,500 bytes, valid CORS origin; original reported fetch error is intermittent, not a confirmed persistent backend outage.

| Module | Current implementation | Preserve | Modify | Delete | Add |
|---|---|---|---|---|---|
| Sidebar | Shared WorkspaceShell, grouped only as market intelligence | Existing routes/themes/settings | Names, grouping, responsive reachability | No capability | Clear research/monitor groups |
| Chat | Native AgentOS streaming/tools | Real runs and current protocol | Failure copy, context/draft, truthful review notice | No execution logic | Explicit history retry/context handoff |
| Suggestions | Four buttons immediately submit | Four topics | Fill and focus before explicit submission | No topic | Predictable editable draft |
| History | Real native SQLite API | Persistent sessions | Same-session reload, race/error guards, titles/time | No records | Dedicated list/detail failure state |
| Overview | Counts, saved facts/events/jobs | All original data and gates | Explain coverage/review limits, contextual links | No data | Investigation entry |
| Data | Filters/evidence/doc extraction | Contracts and saved units | Date/approval language | No workflow | Direct existing comparison entry |
| Events | Filters/acknowledgement/comparison | Source distinctions and checks | Relevant continuation | No evidence | Real event→AI handoff |
| Reports | Deterministic/model generation, read/export/notify | All reports and formats | Direct selection, versions, notification prerequisite | No report | Task result and monitor handoff |
| Monitoring | Saved intervals/coverage/thresholds/schedules | All values and actual schedules | Searchable choices, timezones and next actions | No config | Result links; report context explanation |
| Jobs | Real polling/progress/receipts | Existing execution history | Retry contract, outcome versus approval, result link | No job | Human task names and audit details |

Confirmed defects: selecting current session only pushes the same URL (does not retrigger loading); session errors use generation retry and are not independently cleared; history-list fetch swallows failures as an empty list; jobs exclude interrupted/partial retry even though backend supports them and render all progress with success coloring; report task result.report_id is unused; notifications display an actionable button despite missing configuration; /ask is a distinct advanced capability reachable through retry links under a conflicting assistant name; metadata/IDs dominate key user tasks.

P0/P1 plan and acceptance contract: IMPLEMENTATION_PLAN.md and app/openspec/changes/ux-workflow-p0-p1. OpenSpec strict validation PASS. Original 32 observations remain unreviewed, so original business comparison gates remain BLOCKED; this is not a startup or frontend failure.
