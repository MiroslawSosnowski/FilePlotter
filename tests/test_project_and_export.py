import json
from pathlib import Path

import numpy as np
import pandas as pd

from fileplotter.exporters import export_curves_csv
from fileplotter.importers import DataSourceLoader
from fileplotter.models import Curve, Project, Transform
from fileplotter.project_io import load_project, save_project


def _project_from_csv(path: Path) -> Project:
    source = DataSourceLoader().load(path)
    curve = Curve(
        source_id=source.source_id,
        x_column_id="col_0000",
        y_column_id="col_0001",
        display_label="Load",
        transform=Transform(x_scale=0.5, x_shift=2, y_scale=3, y_shift=-1),
    )
    return Project(
        sources={source.source_id: source},
        curves={curve.curve_id: curve},
        source_x_columns={source.source_id: "col_0000"},
    )


def test_project_round_trip_and_moved_source_relink(tmp_path: Path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text("t,f\n0,1\n1,2\n", encoding="utf-8")
    project = _project_from_csv(source_path)
    project.plot_config.update(
        {
            "title": "Load comparison",
            "background": "#20242b",
            "grid": False,
            "legend": False,
            "line_width": 2.4,
        }
    )
    project_path = tmp_path / "session.fplot.json"
    save_project(project, project_path)
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    assert not Path(payload["sources"][0]["path"]).is_absolute()

    moved = tmp_path / "moved.csv"
    source_path.rename(moved)
    restored, warnings = load_project(
        project_path, relink=lambda _descriptor: moved
    )

    assert not warnings
    restored_curve = next(iter(restored.curves.values()))
    assert restored_curve.transform == next(iter(project.curves.values())).transform
    assert restored.sources[restored_curve.source_id].path == moved.resolve()
    assert restored.source_x_columns == project.source_x_columns
    assert restored.plot_config == project.plot_config


def test_missing_source_is_recoverable(tmp_path: Path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text("t,f\n0,1\n", encoding="utf-8")
    project_path = tmp_path / "session.json"
    save_project(_project_from_csv(source_path), project_path)
    source_path.unlink()

    restored, warnings = load_project(project_path)

    assert warnings and "Missing source" in warnings[0]
    assert not next(iter(restored.sources.values())).available


def test_full_resolution_export_preserves_precision_and_raw_data(tmp_path: Path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "t,f\n0.123456789012345,1.23456789012345\n2.5,3.5\n", encoding="utf-8"
    )
    project = _project_from_csv(source_path)
    source = next(iter(project.sources.values()))
    raw_before = source.get_array("col_0001").copy()
    curve = next(iter(project.curves.values()))
    output = tmp_path / "export.csv"

    export_curves_csv(project, [curve.curve_id], output)
    exported = pd.read_csv(output)

    np.testing.assert_allclose(exported["Load__x"], [2.0617283945061725, 3.25])
    np.testing.assert_allclose(exported["Load__y"], [2.70370367037035, 9.5])
    np.testing.assert_array_equal(source.get_array("col_0001"), raw_before)
