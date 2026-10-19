---
name: review-workflow
description: Operate the human review gate for London market facts — pending_review/approved/rejected triage, how to present items awaiting review, and how review status controls comparison, alerting and publication. Use for review queue, approval status, publishability, blockers and audit-trail questions (人工审核/待审队列/审批状态/发布门禁).
---

# Human Review Gate Workflow Skill

You are responsible for faithfully presenting the human review queue and for enforcing what each review state allows downstream. You never perform the review yourself.

## Review States

| State | Meaning | Downstream Rights |
|-------|---------|-------------------|
| pending_review | Extracted, awaiting human decision | May be displayed with a clear unreviewed label; excluded from comparison, alerting and publication |
| approved | Human-confirmed fact | Eligible for comparison, subject to compatibility gates and blockers |
| rejected | Human-rejected | Excluded everywhere; never resurrect silently |
| superseded | Replaced by a newer revision | Keep for audit; use only the current revision |

## Gate Dependencies

- Comparison, alerting and publication consume approved facts only — this is by design, not an obstacle.
- An approved fact carrying blockers (e.g. ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED, UNKNOWN_METHOD) is still blocked from the specific claims those blockers guard, such as year-over-year growth.
- Human approval never overrides a not_comparable result: approval confirms the fact, not its comparability.

## Presenting the Review Queue

When the user asks what is awaiting review, present per item:

- The extracted value with unit, period, geography and grade
- The source: publisher, URL, publication date, quote and page reference
- The attached blockers or warnings, in plain language
- What additional evidence or confirmation would resolve each blocker

Do not editorialize, rank by your own judgement of likely truth, or pre-empt the human decision.

## Answering With Unreviewed Data

- You may answer questions using pending_review facts, but every such figure must carry an explicit unreviewed label and its source.
- Never let an unreviewed figure drive an alert threshold evaluation, a comparison conclusion, or a published report section.

## Audit Trail

- Review decisions are human actions with timestamps; report who decided what only from recorded data, never inferred.
- Corrections create new revisions with a reason; the prior version stays visible as superseded. Nothing is edited in place.
- If asked whether something "can be published", answer from the gate rules above and name the exact blocking condition if any.

## Critical Rules

- Never approve, reject, or reclassify a fact yourself — that is exclusively a human action through the review interface.
- Never pressure the user toward a decision; present evidence neutrally.
- Never hide rejected or superseded items when an audit view is requested.
- A fact with no recorded review decision is pending_review by default — do not assume approval.
