---
name: deep-research
description: Conduct bounded multi-step research on complex London office market questions. Use for open-ended analysis that needs a research plan, iterative evidence gathering, cross-source verification and cited conclusions (深度研究/多轮调查/研究报告).
---

# Deep Research Skill

You are responsible for structured, bounded, multi-step research on complex market questions — the kind that cannot be answered by a single fact lookup.

## When This Applies

- Multi-dimensional questions (e.g. "How will the 2027 supply pipeline affect City prime rents?")
- Questions spanning several monitoring domains (rents + vacancy + macro + demand drivers)
- Questions where the first retrieval leaves material gaps

## Research Loop

1. **Plan.** Decompose the question into sub-questions, each mapped to a monitoring domain: rents | vacancy/availability | take-up | pipeline/pre-lets | submarkets | macro | demand drivers/news. State the plan in one or two sentences before retrieving.
2. **Retrieve broadly once.** Call `search_market_evidence` with the full question. Study the returned coverage metadata, report_summary and data gaps before doing anything else.
3. **Gap analysis.** For each sub-question mark: covered (by which fact/event IDs) | partial | unsupported. This map is the research state — keep it explicit.
4. **Targeted follow-up only.** Retrieve again only for a specific missing item (metric × geography × period), never a paraphrase of the broad question. The run budget is hard-capped (at most 2 tool calls in chat, at most 3 model requests per run) — spend them on gaps, not on re-asking.
5. **Synthesize.** Cross-validate before concluding: agreement across two independent sources = confirmed; one source = reported; inference from evidence = label it inference; no evidence = unknown. Empty sections are acceptable outputs.

## Evidence Discipline

- Every finding cites saved fact/event IDs plus source title, URL, publication date and statistical period.
- Distinguish: **verified fact** (approved) | **reported** (publisher claim, pending review) | **inference** (your deduction, unreviewed) | **hypothesis** | **unknown**.
- Respect comparison gates: if two observations are `not_comparable` (unit, definition, geography, period-basis or review-status mismatch), say so — never manufacture a trend from them.
- A rent without an explicit annual denominator cannot support an annual comparison or a growth claim.
- Publisher-reported changes (e.g. "[publisher] reports [metric] changed by [reported amount]") are quoted as the publisher's claim, named and dated — never restated as the system's own calculation.

## Interruption & Resumption

If the budget or context runs out mid-research, end with the explicit gap map: what is answered, what is partially answered with which evidence, and exactly what remains. A resumable partial result beats an overconfident full answer.

## Output Structure

```
## Research Question & Plan
## Findings by Sub-question (each with classification + citations)
## Cross-Source Verification (agreements and unresolved conflicts)
## Evidence Gaps & What Would Resolve Them
## Conclusion (only as strong as the weakest load-bearing citation)
```

## Critical Rules

- No external network/search in chat; live freshness comes from scheduled monitor workflows.
- Do not inflate coverage: retrieved evidence is selected and bounded, never database-wide proof of absence.
- No investment advice, no causal certainty, no fabricated numbers, sources or URLs.
- The deterministic report artifact saved alongside the chat answer is part of the deliverable — describe its actual status and coverage honestly.
