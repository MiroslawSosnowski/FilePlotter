from __future__ import annotations

from pathlib import Path

import pandas as pd

from fileplotter.models import Project


def export_curves_csv(
    project: Project, curve_ids: list[str], path: str | Path
) -> None:
    if not curve_ids:
        raise ValueError("Select at least one curve to export.")
    columns: dict[str, pd.Series] = {}
    used: set[str] = set()
    for curve_id in curve_ids:
        curve = project.curves[curve_id]
        source = project.sources[curve.source_id]
        x, y = project.curve_arrays(curve, finite_only=True)
        base = curve.display_label or f"{source.display_name} · {curve.y_column_id}"
        unique = base
        suffix = 2
        while unique in used:
            unique = f"{base} ({suffix})"
            suffix += 1
        used.add(unique)
        columns[f"{unique}__x"] = pd.Series(x)
        columns[f"{unique}__y"] = pd.Series(y)
    pd.DataFrame(columns).to_csv(Path(path), index=False, float_format="%.17g")
