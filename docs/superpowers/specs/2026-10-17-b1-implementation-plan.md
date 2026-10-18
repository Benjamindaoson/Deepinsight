# B1 Implementation Plan

> For agentic workers: use superpowers:executing-plans inline; keep a durable ledger and obtain one fresh independent final review.

**Goal:** implement and actually verify the approved London data foundation.
**Architecture:** native Agno seven-step Workflow; Python domain services; separate SQLite facts/run databases; immutable report snapshots.
**Tech Stack:** Python 3.12, Agno 2.9.0, Pydantic, SQLAlchemy, httpx, PyMuPDF, original UI.
**Spec:** 2026-10-17-b1-market-data-foundation-design.md and acceptance.md in this directory.

## Global constraints
Keep upstream/B0/secrets/A route unchanged. No v3, new scheduler, substitute frontend or new paid service. Four provider requests, 60k input/8k output tokens, 180-second requests/480-second extraction deadline per document execution; evaluation executions are separately identified.

## Review focus
Reject ambiguous rent time basis; validate value against evidence rather than schema alone; exclude source/period/definition mismatches; retry after partial persistence safely; block private address and redirect fetches and document instructions.

## Task 1 — G0/G1 contracts and acquisition
Files: app/london_data/contracts.py, documents.py; app/tests/test_documents.py.
Interface: fetch(url, allowed_hosts) -> snapshot bytes; parse(bytes,type) -> located segments. Observation Pydantic contract consumed by store/comparison.
- [ ] Write tests for source limits, malformed/scanned PDF, real HTML extraction and exact evidence positions; run RED.
- [ ] Implement minimal secure acquisition/parsing; run GREEN and suite.
- [ ] Qualify primary reports and explicit definition evidence; freeze corpus/gold before evaluating heldout output.

## Task 2 — G2 storage and extraction
Files: store.py, extraction.py, skills/extract/SKILL.md; tests/test_store.py, test_extraction.py.
Interface: Repository.save_attempt/persist/query -> stable IDs; extract(document, config) -> preserved raw candidates and metrics.
- [ ] Write failing tests for transactional rollback, idempotent import, revisions, bad/missing evidence and budget refusal.
- [ ] Implement schema migration, versioned attempts and bounded native structured-output extraction.
- [ ] Run full regression; execute a real primary structured-output call and preserve output, no manual masking.

## Task 3 — G3 comparison and runtime
Files: comparison.py, pipeline.py, runtime.py, cli.py, skills/compare/SKILL.md; tests/test_comparison.py, test_pipeline.py.
Interface: compare(old,new) -> result; native Workflow.run(dict) -> export; readonly query tools -> stored facts.
- [ ] Write RED tests for all incompatible dimensions, pp/zero/unit conversion, complete native flow and readonly results.
- [ ] Implement seven steps and AgentOS registration; run GREEN and complete suite.
- [ ] Real workflow/API run and immutable UI browser queries, refresh/restart evidence.

## Task 4 — G4 evidence and review
Files: app/scripts/evaluate.py, acceptance.py, server scripts; b1/docs reports/runbook.
- [ ] Execute 4 documents x 3 independent real extractions with raw scoring, heldout identity preserved.
- [ ] Execute AC-01..30 with failures/recovery and source lineage evidence.
- [ ] Fresh read-only code/data review; fix important findings with regression tests.
- [ ] Recheck protected hashes; final reports reflect actual PASS/FAIL/BLOCKED and exact commands. Stop at B1.

User explicitly authorized continuous implementation; no further plan approval is required. Root is not a Git repository; do not create unrelated history or operate on upstream branches. Log test cycles and decisions in b1/docs/EXECUTION_LEDGER.md instead of Git-only helpers.
