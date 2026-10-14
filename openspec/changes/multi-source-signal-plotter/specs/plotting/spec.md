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

### Requirement: Plot appearance customization
The system SHALL provide a dedicated right-side tab for editing the plot title, axis labels, background and foreground colors, grid, legend, global line width, major tick counts, tick length, and title, label, tick, and legend font sizes. The system SHALL persist those settings in both the project and an application-folder defaults file.
#### Scenario: Customize and reopen a plot
- **WHEN** the user applies custom plot appearance settings and saves the project
- **THEN** the plot updates immediately and the same appearance is restored when the project is reopened.

#### Scenario: Default title from imported file
- **WHEN** the first data source is loaded into a project without a title
- **THEN** the plot title is set to the source file name and remains editable without being overwritten by later imports.

#### Scenario: Reuse application defaults
- **WHEN** the user applies appearance settings without opening a saved project
- **THEN** the settings are written to `plot_settings.json` beside the application and loaded on the next launch.

### Requirement: Clipboard export
The system SHALL copy the currently rendered plot as an image to the operating-system clipboard.
#### Scenario: Paste plot into another application
- **WHEN** the user invokes Copy plot to clipboard
- **THEN** the clipboard contains a rendered image including the current plot styling.
