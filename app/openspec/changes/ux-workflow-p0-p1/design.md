# Design

The user's attached developer brief and explicit instruction authorize native execution through G0-G4 without intermediate approval. Existing Next.js 15 / React 18 / Zustand / nuqs and FastAPI business/native APIs are retained. This directory is an archived working copy, not a Git checkout; preserve a source backup instead of creating a new repository or worktree.

## P0
Track session list errors separately from selected-conversation loading/errors. Fetches are sequence-guarded so stale responses cannot replace a later conversation or clear its error. Clicking an already selected history item explicitly reloads it. A history retry never submits a question. Loading cannot masquerade as an empty conversation. Backend errors remain available in expandable details.

Execution status and evidence approval are separate. Terminal failures/partial/interrupted tasks do not receive success-style progress. Retry eligibility follows the existing backend contract: failed/interrupted/partial refresh/extract only. Successful reports link via real result.report_id.

## P1
Context links contain only a record kind and real ID. Chat resolves current saved records through existing read APIs, displays the source/period/status, prepares an editable question with exact evidence, and never sends automatically. Direct /ask remains a compatible advanced saved-retrieval route, with one primary DeepInsight AI navigation entry.

Evidence drawers foreground quote, date distinctions and limitations; technical provenance stays in details. Data-page comparison reuses existing server eligibility checks. Reports support direct selection, date/cadence/version labels, read/download and monitoring handoff; absent coverage dates remain explicitly unavailable. Monitoring handoff opens existing workspace preferences and never creates a fictitious report-specific subscription. Coverage selections preserve existing unknown values; preferences change only on explicit Save. Unconfigured notifications cannot be sent from the report UI.

## Verification
Freeze baseline source and API state. Run existing tests and regression tests for recovery races, context resolution, retry/status mapping and unknown metadata. Build P0 before P1. Final lint, typecheck, test, production build, local HTTP checks and real-browser flows on desktop/laptop/tablet/mobile, light/dark, history, evidence, comparison, report and monitoring. Real model verification is bounded to a minimal explicit submission; failures are recorded, never replaced with mock success. No external notifications or automatic collection needed for UX acceptance.
