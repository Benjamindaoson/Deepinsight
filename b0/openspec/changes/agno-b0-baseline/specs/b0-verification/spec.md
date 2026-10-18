## ADDED Requirements
### Requirement: Evidence before PASS
The verification harness SHALL save real runtime evidence before assigning PASS and SHALL preserve official tracked source files.
#### Scenario: Model or dependency unavailable
- **WHEN** a required model or dependency is unavailable
- **THEN** the affected test is BLOCKED with its actual error, and no mock output is substituted
### Requirement: Native capability verification
The harness SHALL use native Agno Agent, Workflow, Team, Skills and Scheduler and distinguish backend results from UI support.
#### Scenario: UI lacks workflow navigation
- **WHEN** the backend executes a workflow but the UI lacks a workflow selector
- **THEN** the report records backend and frontend results separately
