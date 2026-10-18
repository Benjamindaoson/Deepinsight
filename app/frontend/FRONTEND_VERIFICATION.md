# Frontend verification receipt

Date: 2026-10-18. Scope: independent business copy under `app/frontend` only. Root task owns backend integration, port 3101, and real-browser acceptance.

## Source and dependencies

- Origin: official `upstream/agent-ui` archive at `6dad9593fca6756e1813e4f4b3b2620be6377691`; no source hardlinks or `.git`, `.env`, old dependencies, or `.next` copied.
- Frozen lock Git blob: `6902c0b9d1b5c8d65b3e15f33526388b0a744b64`, checked equal to original after installation.
- Runtime: WSL Node `v24.18.0`; `npm exec --yes --package=pnpm@10.34.5 -- pnpm`.
- Independent environment: `/home/benjamin/.cache/deepinsight-product-frontend/node_modules`, linked from this frontend. It is not the official/old UI environment.
- Offline frozen installation: PASS, 522 packages reused, zero downloads. Native D-drive import failed twice with EACCES rename; independent Linux virtual-store installation succeeded. Sharp lifecycle build was not approved/executed by pnpm; no dependency versions changed.
- Disposable failed dependency files remain in ignored/excluded `node_modules.failed` and `home` directories after bounded cleanup was rejected by automatic command policy. They are not imported, served, or included in TypeScript checks.

## Commands and observations

All commands run in `/mnt/d/deepinsight-lite/app/frontend` with the Node path above.

| Check | Result |
| --- | --- |
| `pnpm install --offline --frozen-lockfile --package-import-method=copy --virtual-store-dir /home/benjamin/.cache/deepinsight-product-frontend/node_modules/.pnpm` | PASS |
| `pnpm typecheck` | PASS, exit 0 |
| `pnpm lint` | PASS, 0 errors; native AgentOS remote image uses a regular img tag, producing the existing Next image-performance warning |
| `node --experimental-strip-types --test tests/*.test.mjs` | PASS, 3/3 |
| Prettier write on all added/modified TS/TSX UI source | PASS |
| `NEXT_TELEMETRY_DISABLED=1 pnpm build` | PASS, exit 0; all seven business routes and preserved /chat built successfully |

SSE tests verify arbitrary byte splits including UTF-8 and CRLF boundaries, native completion run/citation receipts, interrupted partial text, and provider errors. Earlier typecheck attempts while dependencies were incomplete failed for unavailable tools/modules; these were installation-state failures and are superseded by the successful complete-environment check.

Read-only live API inspection confirmed the overview, settings, comparisons, reports, and documents shapes. No mock records or fixed assistant answers exist in the business UI. Backend progress convention is integer 0–100. Settings accept the exact supported cadence list and show actual UTC cron schedules. Questions are limited to 4,000 characters.

## Acceptance scope

- Implemented: seven business routes, real source refresh actions, evidence and originals, four fact filters and pagination, four event filters, acknowledgements, comparison gates, explicit single-document model extraction, deterministic report generation and read/download, truthful notification receipts, settings save, actual background jobs and retries, bounded polling, deterministic/native SSE answer modes, safe source links and React escaping.
- Preserved: native Agent UI streaming, session, tool, and reasoning components at `/chat`; endpoint defaults to the independent native backend at 7780 and uses a separate persistence key.
- Runtime command: `npm exec --yes --package=pnpm@10.34.5 -- pnpm start`; URL `http://localhost:3101` after build. Root task starts this process and records browser evidence.
- Remaining runtime verification: root-owned browser workflow checks. Passing compile/tests do not stand in for those checks.

## Browser integration repair: fact pagination boundary

Root browser acceptance found that the two option-metadata requests used `limit=1000`, exceeding the actual API maximum of 500. Both now use `/facts?limit=500`. Metadata failures are visible with a retry action instead of leaving an unexplained empty filter. Read-only boundary verification: limit 500 returned 23/23 saved observations, while limit 501 returned HTTP 422. Product API contract for fact pagination is limit 1–500; backend remains the authority for validation.

The comparison picker now shows all saved observations and their original review statuses. Users can submit actual pending observations and see the backend's refusal reasons; the UI does not validate, relabel, or normalize those records. This enables the real blocked-comparison workflow. Source geography labels and comparison dimensions are unchanged.

Repair rebuild: PASS, exit 0 (all routes, lint and generated type validation). Post-build standalone typecheck: PASS, exit 0. An initial parallel typecheck collided with Next replacing its generated .next/types; the sequential check supersedes that transient failure. Root must restart the port-3101 process to consume the new bundle. The frontend agent did not stop that process.

## Final display, retry, thresholds and timing integration

- ISO `YYYY-MM-DD` publication dates render as calendar dates with no invented clock time. Unknown evidence and comparison periods render `Period unknown`.
- Failed refresh/extract jobs alone expose the retry endpoint. Failed Ask/Report jobs link to their respective user flows for an explicit new request.
- The Overview component records `performance.mark('market-overview-primary-ready')` from a React effect after real overview data has committed. It records once per browser document with `detail.fact_count`. On a fresh navigation to `/`, `startTime` is navigation-relative. It is an application commit milestone, not a universal paint or market-data freshness claim.
- Settings include rent and take-up percent-change thresholds and vacancy percentage-point thresholds, with positive bounded number fields submitted in the existing settings PUT.
- Verified the independent native chat defaults to `http://127.0.0.1:7780` and persists under `london-product-endpoint-storage`.

Final sequential verification: Prettier PASS; production build PASS exit 0; standalone post-build typecheck PASS exit 0; SSE protocol tests 3/3 PASS exit 0. No lint errors; the native remote-image performance warning remains. Root retains ownership of the serving process, browser performance readings, and workflow acceptance.

## Explicit optional AI weekly report

Reports adds a separate `Generate AI weekly (model)` button posting `{period: "weekly", include_analysis: true}`. It expects the real HTTP-202 background Job receipt, displays its ID/status, and links to Job Status through the existing action notice. Deterministic daily/weekly buttons still send `include_analysis: false`. The page explicitly labels optional model analysis `REVIEW_REQUIRED`; no schedule, polling hook, or mounting effect requests model analysis. Failed `report_analysis` jobs link back to Reports rather than invoking the refresh/extract retry route.

For this verification turn, the frontend dependency symlink was unexpectedly absent while the approved independent Linux environment remained intact. Restoring that exact symlink required no installation, version change, or source dependency reuse. Root reported no dependency removal. The cause was not established.

Final AI-button verification used an approved isolated Linux source mirror at `/home/benjamin/.cache/deepinsight-product-frontend/build-mirror`. The authoritative source remains `app/frontend`. All 91 source/configuration files matched; `FRONTEND_BUILD_IDENTITY.json` records each SHA-256 and manifest hash `ec474d97c508e8b46b262fcdcae6f423ae779846d31c2d9e46dcca741c80f694`. Mirror `.next` output was copied back to authoritative `app/frontend/.next` after a successful production build.

Sequential final results: Prettier PASS; `CI=1 NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build` in the mirror PASS exit 0 with lint/type validation; post-copy `./node_modules/.bin/tsc --noEmit` in the authoritative project PASS exit 0; SSE tests 3/3 PASS exit 0. The dependency link remained present after these checks. No AI generation request was made by these checks.

Systematic debugging evidence: no lingering frontend install/add/build PIDs remained; frontend tests/package scripts contain no dependency cleanup. A direct `node next/dist/bin/next build` bypassed the pnpm shim's `NODE_PATH`, causing private-hoisted ESLint plugin lookup to fail. This was reproduced with `require.resolve`: plain lookup failed while the shim-equivalent `.pnpm/node_modules` path succeeded. The production build therefore uses the actual frozen `.bin/next` shim. An earlier Next attempt tried to auto-install TypeScript after a link disappearance; its specific build/add PIDs were stopped before completion. The official lock blob still matches `6902c0b9d1b5c8d65b3e15f33526388b0a744b64`, and package devDependencies remained unchanged. The separate cause of intermittent DrvFS link disappearance remains unproven; the isolated Linux build removes that dependency from the build path.

## Rebuild helper handoff

Added only `build-product.sh` and documentation; source TS, package, lock and the 91-file source identity remain unchanged. The helper captures the already-verified Linux mirror procedure, requires existing frozen dependencies, uses the real Next shim, checks absolute paths and source stability, preserves previous output outside source, and does not stop servers or request model/network work. It rejects a live project frontend before its build branch. Root-owned launchers remain authoritative.

Helper verification: `bash -n build-product.sh`, `bash build-product.sh --help`, and read-only `bash build-product.sh --check` PASS. Preflight returned the same 91-file manifest hash `ec474d97c508e8b46b262fcdcae6f423ae779846d31c2d9e46dcca741c80f694`. The full build branch was not rerun for this script-only handoff; the previously verified serving bundle was not replaced.

## Final report-table browser repair and exercised rebuild helper

Reports' existing safe ReactMarkdown reader now enables the already-frozen `remark-gfm` plugin and renders tables inside a horizontal overflow wrapper, with bordered cells and a neutral header. No raw HTML plugin, dependency, API or model behavior changed.

The exact root-owned `product-ui-stop.sh` stopped only verified business UI PID 5429. `bash build-product.sh --build` was then exercised successfully end to end: production build/lint/types PASS; standalone typecheck PASS; SSE tests 3/3 PASS; before/after 91-file identity equal; successful output published back to authoritative `.next`. It preserved the old output and mirror under `/home/benjamin/.cache/deepinsight-product-frontend/build-history/20261018T000225Z-6736`.

The current 91-file manifest is `524f7174db33ae876db0d64084467a6a08208a0b7e2d69df4535aaa767b299a6`, recorded by the helper in `FRONTEND_BUILD_IDENTITY.json`. The exact root-owned `product-ui-start.sh` restarted the product at port 3101 and reported ready. Reports HTTP returned 200.

Real Chrome browser verification opened `/reports` and used `Read report` on saved report `03507af4-ff89-427f-bb74-b14b48997c10`. The modal accessibility tree now exposes a real table with separate Metric/area, Period, Value/unit, Status and Source cells, including original review labels and source links. Visual inspection confirmed aligned rows and headers instead of a pipe-separated paragraph. Screenshot: `report-table-browser-proof.png`. No report generation, model invocation or source refresh was performed. No further source changes followed this verified bundle.



