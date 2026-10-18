## ADDED Requirements
### Requirement: Evidence-backed facts
The system SHALL preserve real report bytes/hash, extraction attempts and precise evidence locations; missing or ambiguous facts SHALL NOT become validated observations.
#### Scenario: Comparable quarters
- WHEN two validated observations have identical required definitions and consecutive quarters
- THEN deterministic decimal comparison SHALL preserve both observation IDs and formulas.
#### Scenario: Incompatible facts
- WHEN any required comparability dimension is unknown or incompatible
- THEN the result SHALL be not_comparable with reasons and no change values.
### Requirement: Native bounded execution
The system SHALL use Agno 2.9.0 Agent/Skills/Tools/Workflow and retain native run IDs, while enforcing the approved request/token/time budgets. The official UI SHALL remain unchanged.
#### Scenario: External failure
- WHEN a fetch, model request or persistence step fails
- THEN the native Workflow SHALL fail without implicit retries and SHALL retain failure evidence and safe usage records.
### Requirement: Reproducible acceptance
All AC-01 through AC-30 in the approved acceptance document SHALL have actual evidence or explicit FAIL/BLOCKED; no test existence or HTTP status alone proves business behavior.
#### Scenario: Business gate is missing
- WHEN a core unit definition, original extraction threshold or human gold review is missing or fails
- THEN B1 SHALL remain FAIL or BLOCKED with the actual evidence, regardless of passing engineering tests.
