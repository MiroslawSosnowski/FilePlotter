# Performance notes

Baseline measured on 2026-10-14 with Python 3.12 on the development Windows
machine:

- Input: comma-delimited CSV, 200,000 rows × 5 numeric columns (11.89 MiB).
- Import time: 7.164 seconds.
- Peak Python allocation reported by `tracemalloc`: 68.11 MiB.

This is a development reference, not a hardware guarantee. CSV parsing uses a
temporary pandas object table before immutable NumPy arrays are cached, so peak
import memory is higher than the steady-state 8 bytes per cached numeric value.
Files are parsed on a worker thread; the UI reports progress and remains event-loop
responsive. Rendering uses pyqtgraph clipping and peak downsampling, while CSV
export reads the complete cached arrays.

The application intentionally has no silent dataset cap. If parsing or allocation
fails, the source is not added and the error is shown. For very large collections,
import sources incrementally and monitor available system memory.
