# Chat-first frontend acceptance

Latest supplement — offline safe publication, 2026-10-18: native streaming draft text is held until a read-only completed-Run publication projection; restored history uses the same projection. UI distinguishes a deterministic evidence fallback from AI limited checks; neither approves facts. Existing failed/cancelled Runs remain errors. Historical browser restore and refresh verified, with **zero new submissions/model calls**. 25 frontend tests, typecheck, lint (existing img warning), production build PASS. Manifest `bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`, 100 source files. Evidence: `app/data/product/evidence/safe-answer-fallback-20261018/REPAIR_ACCEPTANCE_REPORT.md`. New live model streaming acceptance remains NOT RUN; overall product PARTIAL.

2026-10-18 · Scope: `app/frontend` only.

**Core frontend workflow: PASS. Full business/semantic acceptance: PARTIAL.** The product is serving at http://127.0.0.1:3101 with a light-default chat homepage. This report does not approve market facts or supersede the earlier AI business acceptance failure.

## Delivered

- `/` is the native Agno chat homepage; `/chat` uses the same existing ChatArea. `/overview` retains the previous dashboard.
- Shared 288px collapsible sidebar, mobile overlay, New chat, native Session title search, selected chat and existing delete confirmation. Six business navigation links plus Job Status.
- Existing SSE handler, Markdown renderer, Session APIs and AgentOS Run endpoint reused. No second chat database, new framework, new dependency or backend orchestration.
- Light default; persistent Light/Dark via existing next-themes. Shared semantic palette covers chat, tables, inputs, source drawers and notifications.
- Four quick prompts invoke the real Agent. No model invocation on mount, route reads or theme changes. Enter sends, Shift+Enter inserts a newline; generation status, Stop and manual edit-to-retry are present.
- Expandable tool evidence shows metric, geography, period, original value/unit, publisher, review status, quote, source URL, document/record ID and locator. Market Data links carry filters and the active session.
- Native replies/history visibly remain `REVIEW_REQUIRED`. The separate guarded `/ask` is retained. No unqualified trend chart was generated.

## Browser-discovered fixes

1. New chat from a business page could race native query updates. It now performs one route transition.
2. Slow history responses could overwrite a new chat. Responses now check the active session and refuse to overwrite a live stream.
3. Native SSE substring replacement could drop repeated deltas. Deltas are appended; RunCompleted supplies the authoritative final body.
4. Budget/timeout/missing-final-answer failures now explain the incomplete stage. Stop uses the existing native cancellation endpoint; cancellation is cooperative.
5. Chinese punctuation following bare URLs entered Markdown links. Rendering now delimits only exact URLs supplied by retrieved documents. Original saved model text/evidence is unchanged. Reopening the same saved run verified the correction without another model submission.

## Acceptance matrix

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | `/` opens chat | PASS | home-light.png |
| 2 | Welcome and four prompts | PASS | home-light.png, home-mobile.png |
| 3 | Real question invokes Agent | PASS | One browser POST and native run below |
| 4 | Streaming answer | PASS | generating.png, streaming-answer.png, native-stream.txt |
| 5 | Native history restore | PASS | Existing/new sessions reopened after reload |
| 6 | All business navigation | PASS | data/events/reports/monitoring/jobs screenshots and DOM |
| 7 | `/overview` | PASS | Original 32 observations and 29 documents displayed |
| 8 | Theme persistence | PASS | Both selections verified after refresh |
| 9 | Major pages in both themes | PASS for inspected views | Business pages, source drawer and native reply inspected |
| 10 | Tables/citations/errors/loading | PASS within stated tests | Real evidence; offline budget/timeout/missing-answer tests; no forced live provider failure |
| 11 | Preserve backend/data/tasks | PASS for scope | Frontend-only edits; preserved hashes match; all fact items unchanged; no task writes |
| 12 | Desktop/narrow screen | PASS | 390×844, scrollWidth=clientWidth=390; header top=0; composer x=14..376 |
| 13 | Build/lint/TypeScript | PASS | 8/8 offline tests; one pre-existing next/no-img-element warning |
| 14 | Real browser E2E | PASS primary path; PARTIAL exhaustive branches | Prompt → tool → stream → reload → evidence → filtered data → same session. Live cancellation was not exercised with another paid call |

## One real model submission

- Prompt: `What changed in the London office market this quarter?`
- Session: `de25c28a-12d9-46d5-a1a4-1dcb81aa1d89`
- Run: `40315e0e-ba51-4bbb-bf45-345f40d89743`
- Model recorded in native metrics: `claude-sonnet-4-6`. `OpenAI Chat` is the adapter label, not independent verification of the upstream provider.
- Browser POSTs: **1**. Native assistant responses/model calls: **2**. Successful `search_market_evidence`: **1**, returning 13 candidate facts and 4 document references.
- Call 1: input **1,746**, output **16**. Call 2: input **4,661**, output **1,327**.
- Total: input **6,407**, output **1,343**, combined **7,750**. Existing limits 3 calls / 60,000 input / 8,000 output / 1,800 output per request unchanged and respected.
- Native duration **25.619 s**; browser request-to-SSE-completion **25.673 s**.
- Native TTFT **4.190 s** includes the initial tool-directed response and is not visible analysis TTFT. Visible prose was observed by **20.392 s**; exact first prose token is N/A.
- Cost **N/A**, meaning no verified bill, not zero cost. No retry, fallback or second real submission. Later checks read the persisted run.

The nonempty answer explicitly states that verified data is insufficient to confirm change. Candidate numbers match retrieved records and remain unapproved. One semantic limitation remains: `under offer` is rendered “报价中”; the combined 80% must not be interpreted as pre-let alone. The answer remains **REVIEW_REQUIRED**. English prompts receive Chinese answers because the unchanged backend requires Chinese.

## Preservation and limitations

- Facts before/after have identical `items`; only envelope `updated_at` changed (read timestamp). See scope-receipt.json.
- Backend runtime/intelligence and official UI entrypoint hashes match the read-only receipt. No backend restart, provider setting change, raw evidence edit, fact approval, notification or deployment.
- Native chat exposes a labelled raw draft, not the separate business publication gate. `/ask` retains that guarded path. Native completion is not publication approval.
- Search filters the currently loaded native Session page, not every older message server-wide.
- Stop is wired to the native API but was not separately live-tested with another model call. It cannot undo already incurred usage.
- Previous backend test counts were not rerun or relabelled as this task's evidence.
- Inspected browser flows had no captured console errors. Existing image performance lint warning retained; no rule disabled.
- No approved comparable series was established, so no trend plot was added. No PPT or further source investigation.

## Changed files

Functional files: `src/app/layout.tsx`, `page.tsx`, `chat/page.tsx`, new `overview/page.tsx`, `globals.css`, `tailwind.config.ts`; new `src/components/workspace/WorkspaceShell.tsx`; `src/components/market/MarketApp.tsx`; native `ChatArea.tsx`, `ChatInput.tsx`, `MessageArea.tsx`, `MessageItem.tsx`, `Messages.tsx`, new `ToolEvidence.tsx`; native `Sessions.tsx`, `SessionItem.tsx`; `src/hooks/useAIStreamHandler.tsx`, `useAIResponseStream.tsx`, `useSessionLoader.tsx`; `src/types/os.ts`; new `src/lib/chat-evidence.ts`, `chat-errors.ts`; new `tests/chat-evidence.test.mjs`.

Formatting normalized existing ChatArea child/index files. Dependency versions/lockfile unchanged. Frontend-local specification: `openspec/changes/chat-home/proposal.md`. Documentation: this report and PRODUCT_FRONTEND.md.

## Verified commands

From `D:/deepinsight-lite` in PowerShell, using existing independent dependencies:

```powershell
# Stop only business UI
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh
# Build includes lint, typecheck and offline tests
wsl.exe bash /mnt/d/deepinsight-lite/app/frontend/build-product.sh --build
# Start business UI in a hidden window
Start-Process wsl.exe -ArgumentList @('bash','/mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh') -WindowStyle Hidden
# Offline tests only, no model requests
wsl.exe --cd /mnt/d/deepinsight-lite/app/frontend /home/benjamin/.nvm/versions/node/v24.18.0/bin/node --experimental-strip-types --test tests/chat-evidence.test.mjs tests/market-stream.test.mjs
```

Frontend http://127.0.0.1:3101 · Overview http://127.0.0.1:3101/overview · Existing AgentOS http://127.0.0.1:7780.

## Evidence

All files below are under `evidence/chat-home-20261018/`:

- home-light.png, home-dark.png, new-chat.png, home-mobile.png, mobile-sidebar.png
- generating.png, streaming-answer.png, real-answer.png (original rendering), real-answer-evidence.png and real-answer-dark.png (corrected exact source links)
- overview-light.png, overview-dark.png, data-dark.png, evidence-dialog-dark.png, business-page light/dark screenshots
- filtered-data-from-chat.png, citation-render-check.json, browser-checks.json, responsive-receipt.json
- native-stream.txt, native-run.json, raw-answer.md, retrieved-evidence.json, model-call-ledger.json, browser-request-receipt.json, review-checks.json
- facts-before.json, facts-after.json, scope-receipt.json
- build-acceptance.txt, offline-regression-results.txt, server-delivery.out.log, server-delivery.err.log
