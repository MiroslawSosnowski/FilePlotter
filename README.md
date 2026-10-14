# FilePlotter

FilePlotter is a desktop engineering tool for overlaying numeric signals from
multiple comma-delimited CSV files and Excel workbooks. Every source keeps its
own X vector and sample count; the application never resamples or modifies the
input files.

## Setup and run on Windows

```powershell
py -3.12 -m venv .venv
.\run.cmd
```

The application entry point is `main.py`. `run.cmd` invokes it directly with the
existing `.venv`; FilePlotter itself does not need to be installed as a package.
You can also pass a saved project directly to `run.cmd`.

## Workflow

1. Use **File → Add source** and select one or more `.csv` or `.xlsx` files.
   You can also drop those files onto the compact drop area above the source tree.
2. For Excel, choose a worksheet; for every source, choose the one-based header
   row.
3. Right-click a row under **Available signals** and choose **Set as X axis**.
   Double-click any other row to plot or hide it as a Y signal. The current X is
   bold and labelled, while a plotted Y name uses the same color as its curve.
   Every selected Y from that source uses the chosen X. The first file name becomes
   the plot title automatically and remains editable.
4. Select one or more plotted signals to edit X/Y offset and scale, color, line
   style, or primary/secondary Y-axis assignment.
5. Use the scrollable **Plot** tab to edit titles, colors, grid, legend, line
   width, major/minor tick counts, tick length, font sizes, secondary-axis
   visibility, and automatic or manual X/Y ranges.
6. **Apply plot settings** also saves defaults to `plot_settings.json` beside
   the application. A project keeps its own plot settings when saved.
7. Use **Copy plot to clipboard** or `Ctrl+Shift+C` to paste the rendered plot
   into another application.
8. Save a `.fplot.json` project or export a full-resolution transformed CSV,
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
