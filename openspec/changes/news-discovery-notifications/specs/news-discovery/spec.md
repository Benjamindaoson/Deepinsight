## ADDED Requirements
### Requirement: Candidate discovery remains separate from evidence
The system SHALL treat Tavily results as candidate URLs only and SHALL fetch original documents through existing acquisition protections before event extraction.
#### Scenario: Search result has no accessible original
- **WHEN** original acquisition fails
- **THEN** retain a needs_review candidate in job history and create no fact or event from its snippet.
### Requirement: Discovery is bounded and opt-in
The system SHALL require a dedicated locally configured key and explicit enable flag, issue at most one fast search per six-hour window, and reuse durable receipts across retries.
#### Scenario: Only a generic old key exists
- **WHEN** dedicated key is absent
- **THEN** return configuration_missing without an API request.
### Requirement: Delivery statuses are truthful
The system SHALL preserve existing Apprise dedup and unknown-delivery gates, report missing/invalid configuration and never equate local loopback acceptance with external recipient delivery.
#### Scenario: Invalid transport configuration
- **WHEN** transport construction or URL parsing fails
- **THEN** persist a sanitized failure and no stuck sending record.
