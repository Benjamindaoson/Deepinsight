# DeepInsight Lite — London Office Market product

Latest bounded QA result: [FINAL_DELIVERY_REPORT](../FINAL_DELIVERY_REPORT.md).
The newly authorized single Native Agent submission failed during a Windows
usage-ledger file replacement. No second paid submission was performed.
The local persistence fix passed 176 offline/local tests, including a real
Windows sharing-lock reproduction; the complete model flow was NOT retested.
Overall delivery remains PARTIAL. See
`data/product/evidence/provider-receipts-20261018/AI_QA_ACCEPTANCE_REPORT.md`.
Existing collection, publisher change, scheduling and report evidence remains
under `market-closure-20261018`. Human review and formal comparisons stay gated.

Current local product: **http://127.0.0.1:3101**. Double-click `Start-London-Market.cmd` to start it. Seven business pages provide saved market facts, evidence, events, questions, reports, settings and jobs. Native Agent UI remains available at `/chat`.

Latest targeted repair (2026-10-18): [FINAL_DELIVERY_REPORT](../FINAL_DELIVERY_REPORT.md). Business reports and `/api/market/ask` withhold drafts flagged for lease-status quantities, unverified supply trends or model-generated source counts. Raw model history remains an unapproved audit record. No facts were approved; formal historical comparisons remain blocked.

The independent product backend is `london_product.runtime` on 7780, with its own SQLite business/native history under `data/product`. Full operating instructions and actual acceptance results: [product runbook](docs/product/B1_RUNBOOK.md), [product acceptance](docs/product/B1_ACCEPTANCE_REPORT.md), [technical test report](docs/product/B1_TEST_REPORT.md). All unreviewed source values remain labelled; this product authorization does not approve historical B1-G0 or its formal evaluation.

## Historical B1 foundation

London Market Data Foundation on pinned Agno / AgentOS 2.9.0 and unchanged Agent UI.

Business acceptance is **BLOCKED**: annual rent denominator not confirmed, human gold review pending, original heldout extraction threshold not passed. Do not silently infer annual units or present a replay as an original successful evaluation.

Use the verified Windows/WSL commands in [B1_RUNBOOK](../b1/docs/B1_RUNBOOK.md). Independent environment: `.venv`; exact dependencies: `requirements.lock.txt`. Business data and native runtime history are separate SQLite files under `../b1/data/`.

Start from the project root with `app/scripts/start-runtime.ps1`; start UI with `wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/start-ui.sh`. Run engineering checks with `app/scripts/verify-local.ps1`. Only explicit ingest/evaluation/fault-probe commands make real model calls; reading saved results does not re-extract documents (chat itself uses the configured native model).

All 30 actual acceptance records: `../b1/evidence/acceptance-results.json`. Human review: `../b1/docs/B1_HUMAN_REVIEW_CHECKLIST.md`. No B2 jobs or public deployment are included.
