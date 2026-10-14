# Curve Transformations Specification

## ADDED Requirements
### Requirement: Affine X and Y transforms
The system SHALL apply `x_display = x_raw*x_scale + x_shift` and `y_display = y_raw*y_scale + y_shift` independently per curve, with identity defaults.
The curve editor SHALL expose `x_shift` and `y_shift` as X and Y offset controls.
#### Scenario: Shift and scale
- **WHEN** the user sets x_scale=0.001, x_shift=2, y_scale=1000, y_shift=-50
- **THEN** displayed points reflect exactly those equations.

### Requirement: Source preservation
The system SHALL NOT modify the original loaded data or source files when applying transforms.
#### Scenario: Reset curve
- **WHEN** the user resets transformations
- **THEN** the original raw values are displayed again.

### Requirement: Multi-curve editing
The system SHALL support selecting multiple curves and applying the specified parameter values to all selected curves.
#### Scenario: Batch Y shift
- **WHEN** the user selects three curves and sets y_shift=10
- **THEN** all three receive y_shift=10 and their other parameters remain unchanged.

### Requirement: Validation
The system SHALL reject non-finite transform parameters and SHALL warn before applying zero scale.
#### Scenario: Invalid scale
- **WHEN** the user enters NaN as x_scale
- **THEN** the system rejects the input and preserves the prior valid value.
