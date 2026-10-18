# Durable bounded model receipts and concise final analysis

The previous single Native Agent test ended with a provider usage overrun and
lost the exact second-call receipt before Agno completed its metrics. Preserve
every request reservation, formatted request payload, raw provider usage and
parsed usage to an atomic per-run local ledger before propagating any error.
Never log credentials/headers or replace missing usage with estimates.

Keep all existing budgets, model, endpoint, max_tokens=1800 and zero retries.
Make the answer concise: the full record/definition/evidence inventory already
has a UI panel and should not be duplicated as a long generated table. Keep
publisher attribution, pending facts and hypotheses distinct.

Offline provider-boundary regression and full suite precede exactly one newly
authorized browser submission. Failure stops that test without a second submit.
Retain prior source, monitoring and report validation, preserve original facts.

## Actual outcome 2026-10-18

The single real submission failed on Windows atomic-file replacement during
request 2. No second submission was made. The exact runtime lock owner is unknown;
the same WinError5 was reproduced with a real Windows non-delete-sharing reader.
The local fix batches stream persistence and bounds only file-publish retries
to five attempts / 300ms. Persistent failure stops continuation with
AUDIT_STORAGE_ERROR. No model retry or budget increase was introduced.

Final offline/local suite: 176 passed in 31.48s. The post-fix real model path has
not been tested. Overall real-QA status FAIL and product status PARTIAL.
Evidence: app/data/product/evidence/provider-receipts-20261018/.
