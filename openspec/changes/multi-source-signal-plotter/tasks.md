# Implementation Tasks

## Phase 1 — Core data and plot
- [x] Set up PyQt6/PyQtGraph application structure and targeted test harness.
- [x] Implement independent CSV and XLSX source import, worksheet/header selection, validation and loading progress.
- [x] Implement stable source/curve models and independent X column mapping.
- [x] Implement source tree, Y checkboxes and multi-curve overlay with legend, zoom/pan and auto-fit.
- [x] Add a right-side plot customization tab with persistent title, axes, background, grid, legend and line-width settings.
- [x] Add focused tests for import, duplicate column names and different-length X arrays.

## Phase 2 — Curve operations
- [x] Implement immutable affine transform pipeline with numeric X/Y Shift and Scale.
- [x] Add curve selection, batch editing, reset, and parameter validation.
- [x] Add per-curve color, line style and primary/secondary Y-axis assignment.
- [x] Test transform ordering, identity/reset, invalid values and batch edits.

## Phase 3 — Persistence and export
- [x] Implement versioned project JSON save/reload and missing-source relinking.
- [x] Implement PNG/SVG plot export and full-resolution transformed CSV export.
- [x] Test project round-trip, moved files, exported numeric precision and raw-data preservation.

## Phase 4 — Performance and release
- [x] Add cached numeric arrays, rendering downsampling and asynchronous imports.
- [x] Benchmark representative large datasets; document memory/performance limits.
- [x] Run full regression suite and perform manual UI acceptance tests.

## Optional follow-up
- [ ] Mouse-driven interactive curve shifting with synchronization to numeric Shift controls, after UX approval.
