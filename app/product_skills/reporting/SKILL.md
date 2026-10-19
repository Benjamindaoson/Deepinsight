---
name: reporting
description: Generate evidence-cited London office market reports — daily/weekly briefs with deterministic charts, source attribution, quality gates and revision history. Use for market reports, briefs, or exporting findings (日报/周报/市场报告).
---

# Market Reporting Skill

You are responsible for market reports that a reviewer can audit line by line: every number traceable to a saved fact, every chart deterministic, every revision preserved.

## Report Types

| Type | Cadence | Content focus |
|------|---------|---------------|
| daily brief | scheduled (08:00) | new events, source updates, notable changes since last run |
| weekly brief | scheduled (Mon 08:00) | metric movements, pipeline progress, macro context |
| research report | on demand (chat /ask) | scoped answer with findings, charts, gaps and citations |

## Required Structure

1. **Scope** — metrics, geographies and observation period actually covered (from saved data, not from the question's ambition).
2. **Key findings** — only claims that pass the verification gate; each cites saved fact/event IDs.
3. **Observations** — tables of the underlying approved facts with source, period, unit and review status.
4. **Charts** — generated deterministically from saved facts only. A chart never contains a value that is not in the facts table.
5. **Interpretation** — clearly separated from facts; every item labelled inference/scenario with evidence references, and marked unreviewed until human review.
6. **Risks & opportunities** — evidence-based only; unsupported items belong under hypotheses to investigate.
7. **Data gaps** — explicit list of what the report does not cover and why.
8. **Sources** — every cited document with title, publisher, URL, publication date and statistical period.

## Quality Gates (before any report is finalized)

- Rejected and superseded records are excluded; pending_review items appear only as clearly-labelled unverified items or in 待核实 sections.
- No metric change is reported unless the comparison passed the compatibility gate; `not_comparable` pairs are reported as data gaps, not trends.
- Figures with unconfirmed annual denominators are never annualized silently and never drive a growth chart.
- Generation status is recorded honestly (`complete`, `partial`, `withheld` with revision note) — a partial report says what is missing.

## Revision History

- New information never edits history in place: the old report is marked `superseded` with a `revision_reason`, the new report links back to it, and both remain retrievable. Reports are append-only audit artifacts.
- When citing a superseded figure, cite it as historical and name its successor.

## Delivery & Status Honesty

- A report saved to the Reports page exists; one that was only drafted in chat does not. Describe which happened.
- If report generation was skipped, withheld or partially failed, say so and give the recorded reason — never claim a clean run.
- Markdown/HTML artifacts come from the deterministic renderer; do not hand-alter rendered output to fix data problems — fix the underlying record through the review flow instead.
