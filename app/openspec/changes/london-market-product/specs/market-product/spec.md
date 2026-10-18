## ADDED Requirements

### Requirement: Evidence and quality boundaries
The product SHALL retain authentic originals, hashes, source dates and evidence locations and SHALL exclude unreviewed or dimensionally incompatible facts from formal comparisons.

#### Scenario: Unconfirmed annual rent denominator
- **WHEN** a source discloses only GBP per square foot
- **THEN** annual normalized rent remains unknown and comparison returns not_comparable with reasons

### Requirement: Persistent business interaction
The product SHALL expose saved facts, events, reports, settings and job states through seven browser pages, with safe evidence downloads and explicit loading, empty, error and retry states.

#### Scenario: Service restart
- **WHEN** the local service restarts after a completed import
- **THEN** facts and reports remain available and interrupted jobs are explicitly recoverable

### Requirement: Native bounded intelligence
The product SHALL use frozen Agno 2.9.0 Agents, Skills, Tools, Workflows and Scheduler with bounded, explicit model calls, zero SDK retries and deterministic cached reads.

#### Scenario: Repeated extraction
- **WHEN** the same document and extraction version are submitted again
- **THEN** a completed extraction is reused without a new model request

### Requirement: Honest monitoring and delivery
The product SHALL persist independent source failures, deduplicate events and threshold alerts and record notification delivery status without claiming delivery when configuration is missing.

#### Scenario: One source fails
- **WHEN** a public source rejects acquisition
- **THEN** other sources continue and the job records a partial result

#### Scenario: Missing notification configuration
- **WHEN** a user requests a report notification without a configured channel
- **THEN** a configuration_missing receipt is saved and nothing is sent
