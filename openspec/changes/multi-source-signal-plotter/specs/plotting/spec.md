# Plotting Specification

## ADDED Requirements
### Requirement: Interactive overlays
The system SHALL render multiple selected signals with legends, configurable styles, zoom, pan, grid and auto-fit.
#### Scenario: Overlay datasets
- **WHEN** signals from CSV and XLSX are enabled
- **THEN** both appear on the same plot with distinguishable source labels.

### Requirement: Separate Y axes
The system SHALL support assigning a curve to either a primary or secondary Y axis.
#### Scenario: Different units
- **WHEN** force and velocity signals are plotted
- **THEN** the user can assign them to different Y scales.

### Requirement: Export
The system SHALL export the displayed plot to PNG/SVG and selected transformed curves to CSV at original sample resolution.
#### Scenario: Full-resolution export
- **WHEN** plot downsampling is enabled
- **THEN** exported signal data still includes all valid original samples after transforms.

### Requirement: Responsive rendering
The system SHALL keep UI interaction responsive for large datasets through asynchronous loading and rendering optimizations.
#### Scenario: Large source
- **WHEN** a large source is loaded
- **THEN** loading progress and errors are visible and the main UI is not blocked by file parsing.
