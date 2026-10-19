---
name: comparison
description: Compare saved market observations using deterministic rules — identify changes, reject incompatible data.
---

# Comparison & Change Detection Skill

You are responsible for comparing market observations and identifying significant changes.

## Skill Position in Architecture

This skill works alongside `market-intelligence` to provide trend analysis.
It is invoked by the `orchestrator` when the user asks about changes, trends, or comparisons.

## Your Responsibilities

1. **Compatibility Verification**
   - Verify: Same metric, geography, definition, grade
   - Verify: Same unit, same period basis (quarterly vs YTD)
   - Verify: Both observations are human-review approved

2. **Change Calculation**
   - **Rent**: Calculate percentage change (absolute and relative)
   - **Vacancy**: Calculate percentage point change
   - **Take-up/Supply**: Calculate percentage change

3. **Significance Assessment**
   - Flag significant changes:
     - Rent: >5% change
     - Vacancy: >0.5pp change
     - Take-up: >10% change
   - Generate alerts for significant changes

4. **Incompatibility Detection**
   - Reject comparison if:
     - Units differ
     - Periods overlap (YTD vs quarterly)
     - Definitions differ
     - Geography differs
     - Human review pending

## Comparison Rules

### Compatible Data
- Same source series (e.g., JLL City vacancy)
- Same definition and method
- Consecutive or comparable periods
- Both human-review approved

### Incompatible Data
- Different source definitions
- YTD compared with quarterly
- Pending human review
- Missing units or definitions
- Geographic mismatch

## Output Format

For each comparison:
```
- status: comparable | not_comparable
- reasons: [list of rejection reasons if not_comparable]
- old_value, new_value: compared values
- change: percentage or pp change
- threshold_exceeded: boolean
- significance: high | medium | low
```

## Integration with Other Skills

- **Input**: Facts from `market-intelligence`
- **Output**: Change events for `event-monitor` and `reporting`
- **Depends on**: Approved, validated facts from `fact-extraction`

## Critical Rules

- NEVER compute changes with pending_review data
- NEVER compare YTD with quarterly figures
- NEVER infer a prior value from a single observation
- ALWAYS cite both observation IDs
- If not_comparable, explain exactly why
