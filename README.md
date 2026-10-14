# FilePlotter

FilePlotter is a desktop engineering tool for overlaying numeric signals from
multiple comma-delimited CSV files and Excel workbooks. Every source keeps its
own X vector and sample count; the application never resamples or modifies the
input files.

## Setup and run on Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -e ".[test]"
.\run.cmd
```

You can also pass a saved project directly to `run.cmd`.

## Workflow

1. Use **File → Add source** and select one or more `.csv` or `.xlsx` files.
2. For Excel, choose a worksheet; for every source, choose the one-based header
   row.
3. Choose a source X column and check any Y signals in the source tree.
4. Select one or more checked signals to edit X/Y shift and scale, color, line
   style, X override, or primary/secondary Y-axis assignment.
5. Save a `.fplot.json` project or export a full-resolution transformed CSV,
   PNG, or SVG.

Blank, non-numeric, NaN, and infinite samples are reported as gaps and excluded
from rendered/exported X/Y pairs. Duplicate headers remain distinct by physical
column position. Excel formulas are read as cached workbook results; formulas
without a cached numeric result appear as gaps. Missing project sources can be
relinked when a project is opened.

Rendering uses clipping and peak downsampling, while data export always uses the
complete transformed numeric arrays. Source arrays are cached in memory, so the
practical limit depends on available RAM; a rough minimum is 8 bytes per numeric
cell plus pandas parsing overhead during import. Import failures are reported
instead of silently discarding a source.
