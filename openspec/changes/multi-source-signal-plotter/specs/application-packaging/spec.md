# Application Packaging Specification

## ADDED Requirements
### Requirement: Source-only executable build action
The system SHALL expose `Build executable…` in the File menu only while running from source and SHALL omit the action from a PyInstaller-frozen application.

#### Scenario: Build from the development application
- **WHEN** the user chooses `File → Build executable…` and PyInstaller is available in the active Python environment
- **THEN** a non-blocking, cancellable build creates a single windowed `dist/FilePlotter.exe` from the root `main.py` entry point.

#### Scenario: Run the compiled application
- **WHEN** FilePlotter is running as a frozen executable
- **THEN** the File menu does not contain the executable build action.

#### Scenario: Missing build dependency
- **WHEN** the source application is asked to build without PyInstaller installed
- **THEN** it reports the missing optional build dependency without installing software automatically.
