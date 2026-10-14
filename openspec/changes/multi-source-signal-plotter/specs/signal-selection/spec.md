# Signal Selection Specification

## ADDED Requirements
### Requirement: Independent X column
The system SHALL allow each source to define one X column that is shared by every selected Y signal from that source.
#### Scenario: Different sampling rates
- **WHEN** two files use different time vectors and lengths
- **THEN** their curves overlay on the same plot without forced resampling or index-based alignment.

#### Scenario: Change source X mapping
- **WHEN** the user changes the X selector for a source
- **THEN** every selected Y signal from that source is immediately plotted against the new X column.

### Requirement: Multi-select Y selection
The system SHALL expose available Y columns in a compact multi-select dropdown and update plotted curves when visibility changes.
#### Scenario: Select multiple signals
- **WHEN** the user checks multiple Y columns across sources
- **THEN** each chosen signal is displayed with an identifiable legend entry.

### Requirement: Separate mapping and signal inventory
The system SHALL present X/Y axis mapping controls separately from the source's available-signal inventory.
#### Scenario: Inspect a loaded source
- **WHEN** a source is expanded in the left panel
- **THEN** axis selectors appear under `Axis mapping` and file columns appear under `Available signals`.

### Requirement: Stable curve identity
The system SHALL identify curves by source and column IDs, not by display label alone.
#### Scenario: Duplicate headers across files
- **WHEN** two sources both contain `Force_X`
- **THEN** both curves can be selected and configured independently.
