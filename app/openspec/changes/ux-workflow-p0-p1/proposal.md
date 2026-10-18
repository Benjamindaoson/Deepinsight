# DeepInsight Lite P0/P1 workflow improvements

## Why
The existing application runs, but history recovery, execution versus evidence states, result navigation, and cross-page research context interrupt the user's work.

## What Changes
- P0: restore/retry conversations safely; distinguish history/network/model failures, incomplete execution and unreviewed evidence; unify user-facing names and keep all routes.
- P1: group navigation, readable source provenance, contextual research drafts from facts/events/reports, deterministic comparison entry from data, report/job result links, selectable monitoring coverage and honest notification/schedule state.
- Keep the existing architecture, endpoints, histories, data gates, provider configuration, schedules and minimal appearance. No invented data or progress. No automatic model calls from navigation.

## Impact
Primarily app/frontend components, hooks, presentation helpers and tests. Existing business and native APIs remain compatible. Evidence and acceptance records live in root docs/ux. No changes to the sibling Radar project or upstream checkouts.
