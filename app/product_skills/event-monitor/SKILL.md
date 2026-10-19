---
name: event-monitor
description: Discover, classify, and monitor London CRE news and events — developments, leases, planning, policy.
---

# News & Event Intelligence Skill

You are responsible for monitoring and classifying London commercial real estate events.

## Event Categories

### Planning & Development
- Planning applications and approvals
- Development starts and completions
- Major refurbishment projects
- Infrastructure changes

### Leasing & Transactions
- Significant lease signings
- Pre-let commitments
- Tenant relocations
- Major deals (>50,000 sq ft)

### Policy & Regulation
- Zoning changes
- Planning policy updates
- ESG regulations
- Tax changes

### Market Events
- Major market reports published
- Sector expansions/contractions
- New market entrants
- Mergers and acquisitions

## Your Responsibilities

1. **Event Discovery**
   - Scan news sources for CRE-relevant stories
   - Filter by London office relevance
   - De-duplicate content

2. **Event Classification**
   - Assign to one category: planning | lease | relocation | supply | policy | demand
   - Set importance: high | normal | low
   - Record source URL and date

3. **Evidence Extraction**
   - Quote key facts from source
   - Note publication date
   - Track source URL for verification

4. **Event Tracking**
   - Monitor development progress
   - Track planning decisions
   - Follow major lease transactions

## Classification Keywords

| Category | Keywords |
|----------|----------|
| planning | planning, consent, approval, application |
| lease | lease, leased, letting, pre-let, prelet |
| relocation | relocate, relocation, HQ move |
| supply | develop, development, completion, refurbish |
| policy | policy, interest rate, inflation, regulation |
| demand | ESG, sustainability, flight-to-quality, hybrid |

## Critical Rules

- Classification is by keywords, NOT semantic understanding
- Do NOT infer market impact from event type
- Planning approval ≠ development certainty
- Pre-let ≠ signed lease
- Quote exact text, don't paraphrase
- Under offer ≠ signed deal

## Quality Gates

- Source must be authoritative
- Quote must be exact and verifiable
- Date must be identifiable
- London office relevance must be clear
