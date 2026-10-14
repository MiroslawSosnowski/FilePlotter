# Project Persistence Specification

## ADDED Requirements
### Requirement: Save and reload session
The system SHALL save source references, worksheet/header selection, column mapping, curve visibility, styles, transforms and axis settings in a versioned JSON project.
#### Scenario: Reopen project
- **WHEN** a saved project is reopened with unchanged source files
- **THEN** the same curve configuration and plot are restored.

### Requirement: Missing source recovery
The system SHALL identify missing or changed sources and offer relinking rather than silently substituting data.
#### Scenario: File moved
- **WHEN** a referenced CSV is missing
- **THEN** the project opens with a clear missing-source warning and allows the user to locate the file.
