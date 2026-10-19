# DeepInsight Lite: runtime and integration boundary

This document describes the source snapshot, not a claim that every market
indicator has passed human review. The current product runtime is
`app/london_product/runtime.py:create_app`; the business frontend is
`app/frontend`. Agno AgentOS owns the registered market Agent, Workflow runs,
sessions, and Scheduler. FastAPI exposes the product's deterministic read and
write APIs alongside AgentOS. SQLite stores market facts and product jobs; a
separate Agno database stores native runs and sessions.

## One business loop

```text
registered source -> fetch/parse -> original snapshot + hash
  -> extraction/validation -> reviewed or pending market fact/event
  -> strict Python comparison -> evidence-backed signal
  -> Agent analysis or Workflow report -> publication gate
  -> UI query/report; configured notification only after authorization
```

The product never sends a normal saved-data lookup to a model solely to read
SQL. The router uses deterministic queries for those requests. An explanatory
question enters the Agno Agent, which loads relevant native Skill instructions,
calls evidence tools, and produces a draft. The publication gate binds claims
to retrieved evidence and may show a labeled deterministic safe answer instead
of publishing an unsupported draft. Long-running collection, comparison,
reporting, and research use registered Agno Workflows with native run IDs.
Monitoring uses the existing Agno Scheduler. Python, rather than the model,
decides numeric arithmetic and comparability.

## Source ownership

| Concern | Current canonical source | Boundary |
| --- | --- | --- |
| Browser chat and business pages | `app/frontend/src` | Agno SSE/session APIs and `/api/market` |
| Product composition | `app/london_product/runtime.py` | One AgentOS registration point |
| Market facts, events, jobs | `app/london_product/service.py`, `store.py` | SQLite; review status preserved |
| Source collection | `app/london_product/sources.py`, `structured_sources.py` | External text is untrusted data |
| Question routing and evidence | `app/london_product/query_router.py`, `qa_context.py`, `temporal_search.py` | Bounded context; evidence IDs |
| Model and publication gates | `app/london_product/intelligence.py`, `analysis_guard.py`, `safe_answer.py` | Drafts never approve facts |
| Native skills | `app/product_skills/*/SKILL.md`, `app/london_product/skill_registry.py` | Skill loading is separate from tool execution |
| B1 deterministic contracts | `app/london_data/contracts.py`, `comparison.py`, `validation.py`, `extraction.py` | Pure functions reused by product |
| Frozen upstream | `upstream/agno`, `upstream/agent-ui` | Git submodules; no local fork edits |

`app/london_data/runtime.py` is a historical B1 AgentOS entry point. It is not
the product's default server. The product currently reuses the B1 package's
deterministic comparison, precision, and bounded-model helpers. The
`app/product_skills/_core` experiments have no production Python import path;
they are not part of this public source snapshot and should not be described
as active Agno behavior.

## Target physical consolidation

Keep the single `app/london_product/runtime.py` composition root and the
existing AgentOS identity. Move reusable B1 pure contracts under a stable
domain namespace only after their callers and tests are migrated. Keep market
facts in the product SQLite store and Agno runs in its native store; do not
start another online B1 database. Split the large frontend market page by
route without replacing the Agno chat/SSE/session implementation. Finally,
remove historical runtime launchers only after all documented startup paths
and deployment commands point to the same product entry. These are remaining
code-consolidation tasks, not changes claimed by this source publication.

## Evidence and deployment limits

The distributable offline fixture at `app/fixtures/offline_evidence.json` is a
saved public-evidence receipt for a model-free demonstration. Original market
documents, the live SQLite database, human review records, model transcripts,
secrets, and the accepted local frozen build live in ignored paths. A fresh
GitHub clone therefore does not reproduce the full local acceptance state or
turn pending facts into approved facts. The local frozen release pointer under
`docs/delivery/` is intentionally not a source-repository launch contract.
