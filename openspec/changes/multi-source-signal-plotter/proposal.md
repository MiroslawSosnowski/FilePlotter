# Proposal: Multi-Source Signal Plotter

## Why
Engineers need a responsive desktop tool to overlay and compare signals from multiple CSV and Excel files without modifying raw data or forcing identical sampling grids.

## Scope
- Load multiple comma-delimited CSV and XLSX workbooks, select Excel sheets and header rows.
- Select an independent X column per source and any number of Y signals via checkboxes.
- Overlay signals and control visibility, appearance, legends, zoom/pan and auto-fit.
- Apply per-curve affine transformations to X and Y; support multi-selection and numeric editing.
- Export plots and transformed data; save/reopen projects.
- Handle missing/non-numeric values and large datasets safely.

## Non-goals
- Editing original source files.
- Automatic time alignment, resampling or interpolation.
- Full signal processing (FFT, filters) in initial release.

## Decisions
- Interactive mouse-drag shifting remains an optional enhancement; numeric controls are mandatory.
- Missing project sources remain visible and unavailable, with an explicit file-picker relink prompt on open.
- XLSX formulas are imported from cached workbook results; missing cached numeric values are reported as gaps.
