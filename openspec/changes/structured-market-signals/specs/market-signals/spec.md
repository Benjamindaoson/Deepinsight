## ADDED Requirements

### Requirement: Official structured sources
The product SHALL fetch only fixed, registered public HTTPS endpoints for planning and labour data, bound response size and timeout, preserve raw bytes and source URL, and mark derived signals pending review. A source failure SHALL leave other source outcomes intact. Absence of an EPC bearer token SHALL be explicit and SHALL NOT trigger a network request.

#### Scenario: Public planning and labour feeds are available
- **WHEN** a scheduled refresh reaches the official planning and Nomis endpoints
- **THEN** the product preserves originals and hashes, extracts schema-checked candidate records, and records pending-review provenance without approving a market trend

#### Scenario: EPC token is absent
- **WHEN** EPC acquisition is considered without a configured token
- **THEN** the source reports `configuration_missing` and makes no EPC request

### Requirement: Low-latency answer routing
The product SHALL route saved factual lookups to deterministic code using local storage and SHALL route open-ended interpretation to the existing native Agent. The router SHALL NOT treat an unapproved observation as a verified trend. No user question SHALL initiate a whole-catalog external refresh.

#### Scenario: User asks for a saved metric
- **WHEN** the user requests a bounded saved-data lookup
- **THEN** the answer streams saved evidence without a model or external-source request and keeps the review state visible

#### Scenario: User requests interpretation
- **WHEN** the user asks for risks, opportunities, causes or a trend explanation
- **THEN** the request follows the existing Agent path with its budget and publication checks
