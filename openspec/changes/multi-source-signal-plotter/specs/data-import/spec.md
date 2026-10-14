# Data Import Specification

## ADDED Requirements
### Requirement: Multiple CSV sources
The system SHALL load multiple comma-delimited CSV files into independent data sources without replacing already loaded sources.
#### Scenario: Add another CSV
- **WHEN** the user imports a second CSV
- **THEN** the first source remains available and columns from both sources can be plotted.

#### Scenario: Drop data files
- **WHEN** the user drops one or more CSV or XLSX files onto the compact source drop area
- **THEN** each supported file enters the same worksheet and header-row import flow as files selected through the file dialog.

### Requirement: Excel worksheets
The system SHALL support XLSX imports with worksheet selection and configurable header row.
#### Scenario: Select worksheet
- **WHEN** a workbook contains multiple worksheets
- **THEN** the user can choose a worksheet and inspect its available columns.

### Requirement: Robust parsing
The system SHALL identify numeric columns, missing values and malformed data and SHALL provide actionable errors rather than silently coercing ambiguous values.
#### Scenario: Missing numeric samples
- **WHEN** a selected signal contains blank or non-finite samples
- **THEN** invalid points are handled as gaps or omitted consistently and the user is informed of their count.
