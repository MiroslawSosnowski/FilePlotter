# Signal Selection Specification

## ADDED Requirements
### Requirement: Independent X column
The system SHALL allow each source to define one X column that is shared by every selected Y signal from that source.
#### Scenario: Different sampling rates
- **WHEN** two files use different time vectors and lengths
- **THEN** their curves overlay on the same plot without forced resampling or index-based alignment.

#### Scenario: Change source X mapping
- **WHEN** the user right-clicks a signal row and chooses `Set as X axis`
- **THEN** every selected Y signal from that source is immediately plotted against the new X column.

### Requirement: Multi-select Y selection
The system SHALL toggle an available Y column between plotted and hidden states when its signal row is double-clicked.
#### Scenario: Select multiple signals
- **WHEN** the user double-clicks multiple Y-column rows across sources
- **THEN** each chosen signal is displayed with an identifiable legend entry.

#### Scenario: Identify plotted signals
- **WHEN** a Y signal is plotted
- **THEN** its row label uses the same color as its curve and its status indicates that it is plotted.

### Requirement: Separate mapping and signal inventory
The system SHALL present X/Y assignments directly in the source's available-signal inventory without separate dropdown selectors.
#### Scenario: Inspect a loaded source
- **WHEN** a source is expanded in the left panel
- **THEN** file columns appear under `Available signals`, the current X row is clearly labelled, and plotted Y rows use their curve colors.

### Requirement: Stable curve identity
The system SHALL identify curves by source and column IDs, not by display label alone.
#### Scenario: Duplicate headers across files
- **WHEN** two sources both contain `Force_X`
- **THEN** both curves can be selected and configured independently.
