# DeepInsight Lite UX P0/P1 Implementation Plan

> Native execution in this session using Superpowers executing-plans. One independent review at the end.

**Goal:** Preserve every current business page and connect research, evidence, events, reports and monitoring.
**Architecture:** Existing Next.js frontend and existing APIs; no core Agent or scheduler changes.
**Tech Stack:** Next.js 15.5.18, React 18.3.1, Zustand, nuqs, Tailwind, native Node test runner; Python project .venv remains unchanged.
**Spec:** app/openspec/changes/ux-workflow-p0-p1/ plus the user's attached brief.

## Global Constraints
- Only D:/deepinsight-lite. Preserve all original records and source gates. No new dependencies.
- No fake data, verification, progress, history, capability, or notification success.
- No automatic model submission from a context link, suggested question or navigation.
- Do not change current monitoring settings or collect external data for a visual check.
- A source zip replaces a Git baseline because this working copy has no .git.

## Review Focus
- Slow history A after selecting B: ignore A success and failure, including after a new chat.
- One record ID missing or containing special characters: encode identity, show failure, never synthesize context.
- Terminal job and unknown progress: no implied success; retries match actual API contract.
- Report body A arrives after B: retain only B; deep links open the correct saved record.
- Monitor options not in current catalog: preserve saved values until explicitly edited.

## Task 1: P0 reliability
Files: store.ts, useSessionLoader.tsx, Sessions.tsx, SessionItem.tsx, ChatInput.tsx, chat-errors.ts, MarketApp.tsx, market-api.ts, workflow.ts; tests/ux-workflow.test.mjs.
- [x] Write regression tests for a selected-session reload controller and task outcome/retry helpers; run RED.
- [x] Implement request identity guard, dedicated list/detail errors and explicit same-session retry; friendly generation errors retain diagnostics.
- [x] Match job retry eligibility to backend; expose real report IDs; disable unavailable notifications; unify names.
- [x] Run tests/typecheck and production build; record P0 result.

## Task 2: P1 connected research
Files: workflow.ts, ResearchContext.tsx, ChatInput.tsx, WorkspaceShell.tsx, Sessions.tsx, SessionItem.tsx, MarketApp.tsx, globals.css.
- [x] Add RED tests for record resolution, prompt metadata/unknowns and result links.
- [x] Add editable contextual drafts from real API records, preserve evidence states, no auto-send.
- [x] Add evidence actions, data comparison entry, report deep links/monitor handoff and grouped navigation.
- [x] Replace identifier text input with searchable selections preserving saved values; explain schedule timezone and notification requirements.
- [x] Run tests/typecheck/build and record G1-G3.

## Task 3: Runtime acceptance
- [x] Final lint/typecheck/test/build and exact source/build identity check.
- [x] Real browser: home/suggestion and existing-run restoration (fresh live-model send remains BLOCKED), evidence→AI, event→AI, data comparison, history away/return/retry, task→report→download→monitor; negative missing-record flow.
- [x] Responsive 1440/1280/820/375 and light/dark screenshots; check console and focus.
- [x] Fresh reviewer checks changed source; repair meaningful findings with regression tests.
- [x] Write docs/ux/G4_FINAL_ACCEPTANCE.md, preserve actual screenshots and remaining blockers.
