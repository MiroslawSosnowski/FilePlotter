# Design

## Stack
Python 3.12+, PyQt6, PyQtGraph, NumPy, pandas, openpyxl. JSON for project metadata. Use model/view separation.

## Data model
- `DataSource`: stable source ID, path, format, sheet (for XLSX), header-row index, column metadata, immutable raw data handle.
- `Curve`: stable curve ID, source ID, X column, Y column, visibility, display label, color/style, axis assignment, transformation parameters.
- `Transform`: x_scale=1, x_shift=0, y_scale=1, y_shift=0.
- `Project`: version, source descriptors, curves, plotting configuration; store relative paths where feasible.

## Transform semantics
`x_display = x_raw * x_scale + x_shift`
`y_display = y_raw * y_scale + y_shift`
Scaling is applied before shifting. Shifts use displayed-axis units. Negative scales are permitted, zero scales require an explicit warning because they collapse an axis. Numeric inputs must reject NaN and infinity.

## UI
Left panel: source tree (CSV files, XLSX sheets), X-column selectors, Y-signal checkboxes. Center: interactive plot. Right/bottom: selected-curve properties and numeric transform editor. Multi-selection edits are explicit: apply same absolute parameter values to all selected curves; preserve non-edited properties. Show transformed values on hover/cursor readout.

## Performance
Read files off the UI thread; cache parsed raw numeric columns, avoid per-frame full-file reloads. Use PyQtGraph clipping/downsampling for rendering only. Exports operate on full-resolution transformed values. Preserve distinct X vectors, lengths and sampling intervals. Bound memory and report failures rather than silently dropping datasets.

## Integrity
Raw arrays are read-only from the transformation layer. Project files never embed or overwrite input data. Validate paths, sheet/column identities and project schema version on reopen. Missing sources show a recoverable warning; no fabricated data.

## Verification
Unit tests for affine transforms, column validation, serialization and non-mutation; integration tests for CSV/XLSX import, multiple independent X axes, exports and project reload; targeted UI smoke tests for selection and plot updates. Run full suite at release checkpoints.
