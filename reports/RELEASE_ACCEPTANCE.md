# Release acceptance — 19 October 2026

Engineering changes are verified. The complete AI market-intelligence business acceptance remains conditional on provider availability and eligible evidence.

- New briefing requests execute the existing Agno research workflow. Missing evidence produces a partial or insufficient-evidence result rather than an unconditional success.
- Evidence audits and report follow-ups retain the selected report ID and create no replacement report. Audits expose original-file/quote checks, literal-number support, current review state and finding-level verifier outcomes. These checks do not grant semantic or human approval.
- Specific data queries and monitoring requests follow distinct read operations. Schedule requests return a specific blocked response when the runtime has no active scheduler.
- Customer-facing publication labels, fallback reasons, report text and exports use English. Raw requests and original documents remain internal provenance, not generated answers. Unsupported model drafts remain withheld.
- A real browser sequence exercised report creation and an audit of that report. JSON/HTML/Markdown exports were read back. Nine frontend routes and their main backend resources were checked over HTTP.
- Local frozen regression: **578 backend tests passed**, **33 frontend tests passed**, type checks and production build passed. The curated source tree independently started without model credentials and passed **8 self-contained emergency regressions**.
- An actual Agno clock poll claimed a due schedule and called the isolated monitoring endpoint. The free Bank of England source failed with `ConnectError`; the job and schedule run correctly recorded failure and HTTP 503. This is evidence of scheduling and failure propagation, not successful live-market monitoring.
- No new paid model call, fact approval or external notification was made. A previous controlled provider attempt returned insufficient quota. Jev remains optional and requires a dedicated credential.

Historical replay tests require local source originals and receipts excluded from public source control. Their local pass count does not assert that private fixtures ship with this repository or that a new live AI evaluation passed. Use the focused test command in the README for the self-contained emergency regression.

Temporary databases, build products, acceptance snapshots, programming-tool metadata, private research receipts and obsolete development reports are excluded from the public release tree. Original local evidence is retained. Git history is not rewritten.
