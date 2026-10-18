# G2 — conversation and Agent experience

Status: **PASS for input, restored history and error recovery; PARTIAL for a fresh live-model successful final answer**, which was not re-run. See G4 for the precise model and version boundaries.

History list failure, conversation restore loading/error, generation failure and evidence approval have separate UI states. Clicking the selected conversation repeats a real read; Reload this conversation never submits a model request. Sequence, URL, active-run, endpoint and authentication guards reject stale history results. List failures are no longer silently turned into empty history. New/different conversations reset unsent composer state.

Errors distinguish connection, configuration, unavailable service, no usable source, timeout, budget and incomplete output. Technical diagnostics are available in details. The concurrent main-delivery additions for provider-reported usage/missing receipts and restored failed runs are preserved. Failed native history is never displayed as a completed answer; its question can be edited without automatic resubmission. Any complete response is still labelled AI interpretation, with source periods and review requirements.

Machine validation and human approval travel separately. The assistant context includes actual record identity, quote, period, available source URL/dates, machine_validation_status and human_review_status. Only explicit human approval permits human-reviewed copy. No confidence score or approved market value was invented.

Actual browser evidence: existing completed native conversation eb36e907-46cb-41c3-818a-a4341864a2eb restored, navigated away/returned; missing conversation retried with actual GET requests and zero model POSTs; keyboard Delete opened confirmation and Cancel preserved the record. The controlled run bc3d6a09-34db-47b5-9771-2a4cb5f449d1 from the main delivery session failed after retrieval with Windows ledger replacement WinError 5. Its persisted ERROR state was checked in this UI. It is retained as failure evidence, not a successful analysis.

No new paid model request was initiated by this UX task. The main delivery session reported its local ledger repair and backend restart; no second paid submission is authorized for this acceptance. A real deterministic /ask request returned saved observations/citations without invoking the model. Final status and explicit model-success blocker: G4_FINAL_ACCEPTANCE.md.
