---
name: fact-extraction
description: Extract, normalize, and structure London CRE market observations from publisher evidence.
---

# Fact Extraction & Normalization Skill

You are responsible for extracting structured market facts from raw source content.

## Your Responsibilities

1. **Metric Extraction**
   - Extract: Prime Rent, Grade A Rent, Vacancy Rate, Availability, Take-up, Supply Pipeline
   - Identify: Development completions, refurbishments, pre-let commitments
   - Track: Submarket areas (City, West End, Canary Wharf, Midtown/Fringe)

2. **Evidence Preservation**
   - Record exact quote from source text
   - Note page number and character position
   - Preserve source URL and publication date
   - Do not modify or interpret the quote

3. **Unit Normalization**
   - Convert all rents to GBP/sq ft/year
   - Convert all areas to sq ft (from sq m if needed)
   - Standardize percentages
   - Note currency if not GBP

4. **Period Standardization**
   - Identify: Quarterly vs YTD vs annual figures
   - Normalize to: YYYYQN format (e.g., 2026Q2)
   - Flag YTD figures that cannot be converted to quarterly

5. **Geography Standardization**
   - Map to standard submarket names:
     - "Square Mile", "City", "Bank" → "City"
     - "West End", "Oxford Street", "Bond Street" → "West End"
     - "Canary Wharf", "Isle of Dogs", "Docklands" → "Canary Wharf"

## Critical Rules

- **Rent units**: MUST include time denominator. "£/sq ft" without "per annum" = unknown annualization. Flag as needs_review.
- **Vacancy vs Availability**: These are different metrics. Never substitute.
- **YTD vs Quarterly**: Do NOT compute quarterly from YTD by subtraction.
- **Pre-let vs Under offer**: These are different statuses. Preserve as-is.
- **Quotes**: Must be exact contiguous text from source. No paraphrasing.

## Definition Recording

For each fact, record:
- `metric`: rent/vacancy/takeup/etc
- `value`: numeric value
- `unit`: GBP/sq ft/year, %, sq ft
- `period`: YYYYQN format
- `geography`: standardized submarket name
- `grade`: Prime/Grade A/not applicable
- `definition`: source's own definition of the metric
- `basis`: quarterly/YTD/annual
- `method`: how the metric was calculated
- `source`: document URL and title
- `evidence`: exact quote and locator

## Quality Gates

Extract facts only if:
1. Quote is exact and verifiable
2. Value has unit clearly stated
3. Period is identifiable
4. Geography is mappable
5. Metric is definable

Return `null` for any unknown field. Never fabricate data.
