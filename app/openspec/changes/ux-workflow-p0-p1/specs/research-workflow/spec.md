## ADDED Requirements

### Requirement: Recoverable conversation history
The UI SHALL distinguish history-list failure, conversation loading, conversation failure and generation failure. Explicit retry SHALL reload the same conversation without a model request. Stale responses SHALL NOT overwrite a later selection or live generation.

#### Scenario: Retry the selected conversation
- **WHEN** loading a selected conversation fails and the user retries
- **THEN** the same read request is made, its error can clear on success, and no generation is submitted

### Requirement: Truthful execution and evidence state
The UI SHALL distinguish successful execution from approved evidence and SHALL expose backend-supported retry and actual result links.

#### Scenario: An interrupted extraction
- **WHEN** an extraction has interrupted status
- **THEN** a retry is offered and the task is not presented as successful

### Requirement: Contextual research handoff
The UI SHALL resolve the real selected fact, event or report and prepare an editable research question with identity, available period and evidence. Navigation SHALL NOT initiate model execution.

#### Scenario: Continue from a fact
- **WHEN** a user chooses Analyze with AI on a saved observation
- **THEN** the assistant displays that record's context, prepares a draft and waits for explicit submission

### Requirement: Coherent report and monitoring workflow
The UI SHALL open a report from its actual task result, retain exports, disclose unknown coverage dates, explain notification prerequisites and preserve monitor preferences unless explicitly saved.

#### Scenario: Open a report result and monitor its coverage
- **WHEN** a user follows a completed report task and then opens monitoring
- **THEN** the actual report is identifiable and existing workspace settings are shown without automatic mutation

### Requirement: Accessible preserved business pages
All existing routes and light/dark themes SHALL remain usable. Keyboard focus, small-screen navigation, readable limitations and overflow containment SHALL be verified.

#### Scenario: A narrow viewport
- **WHEN** the workspace is opened at 375 pixels wide
- **THEN** navigation and main tasks remain reachable and the viewport has no unintended horizontal overflow
