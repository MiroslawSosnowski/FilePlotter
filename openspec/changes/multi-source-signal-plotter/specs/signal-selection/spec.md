# Signal Selection Specification

## ADDED Requirements
### Requirement: Independent X column
The system SHALL allow each source to define its own X column, with a per-curve override when required.
#### Scenario: Different sampling rates
- **WHEN** two files use different time vectors and lengths
- **THEN** their curves overlay on the same plot without forced resampling or index-based alignment.

### Requirement: Checkbox Y selection
The system SHALL expose available Y columns as checkboxes and update plotted curves when visibility changes.
#### Scenario: Select multiple signals
- **WHEN** the user checks multiple Y columns across sources
- **THEN** each chosen signal is displayed with an identifiable legend entry.

### Requirement: Stable curve identity
The system SHALL identify curves by source and column IDs, not by display label alone.
#### Scenario: Duplicate headers across files
- **WHEN** two sources both contain `Force_X`
- **THEN** both curves can be selected and configured independently.
