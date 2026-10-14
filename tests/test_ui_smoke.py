from pathlib import Path
from dataclasses import replace

import pytest
from PyQt6.QtWidgets import QApplication

from fileplotter.app import MainWindow
from fileplotter.importers import DataSourceLoader
from fileplotter.models import default_plot_config


def _select_all_y(window: MainWindow, source_id: str) -> None:
    for action in window._source_y_selectors[source_id].menu().actions():
        action.setChecked(True)


def test_source_selectors_create_curves_and_share_x(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,signal,x2\n0,2,10\n1,4,20\n", encoding="utf-8")
    source = DataSourceLoader().load(path)
    window = MainWindow()
    qtbot.addWidget(window)

    window._source_loaded(source)
    _select_all_y(window, source.source_id)

    root = window.source_tree.topLevelItem(0)
    assert root.child(0).text(0) == "Axis mapping"
    assert root.child(1).text(0) == "Available signals"
    assert window.plot_title.text() == "signals.csv"
    assert window.project.plot_config["title"] == "signals.csv"
    assert len(window.project.curves) == 2
    assert len(window.plot._items) == 2
    x_selector = window._source_x_selectors[source.source_id]
    x_selector.setCurrentIndex(x_selector.findData("col_0002"))
    assert window.project.source_x_columns[source.source_id] == "col_0002"
    assert all(
        curve.x_column_id == "col_0002"
        for curve in window.project.curves.values()
    )
    assert not window.project.curves[
        next(
            curve_id
            for curve_id, curve in window.project.curves.items()
            if curve.y_column_id == "col_0002"
        )
    ].visible


def test_batch_transform_preserves_unedited_values_and_reset(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,a,b\n0,2,3\n1,4,5\n", encoding="utf-8")
    source = DataSourceLoader().load(path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._source_loaded(source)
    root = window.source_tree.topLevelItem(0)
    _select_all_y(window, source.source_id)
    signals_group = root.child(1)
    first_item, second_item = signals_group.child(1), signals_group.child(2)
    curves = list(window.project.curves.values())
    curves[0].transform = replace(curves[0].transform, x_shift=1)
    curves[1].transform = replace(curves[1].transform, x_shift=2)
    first_item.setSelected(True)
    second_item.setSelected(True)
    window._selection_changed()

    window.transform_inputs["y_shift"].setValue(10)
    window._apply_transform()

    assert [curve.transform.x_shift for curve in curves] == [1, 2]
    assert [curve.transform.y_shift for curve in curves] == [10, 10]
    window._reset_transform()
    assert all(curve.transform.x_shift == 0 for curve in curves)
    assert all(curve.transform.y_shift == 0 for curve in curves)


def test_plot_customization_tab_applies_and_resets_settings(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,signal\n0,2\n1,4\n", encoding="utf-8")
    window = MainWindow()
    qtbot.addWidget(window)
    window._source_loaded(DataSourceLoader().load(path))
    source_id = next(iter(window.project.sources))
    _select_all_y(window, source_id)
    monkeypatch.setattr(
        "fileplotter.app.save_plot_settings",
        lambda config: tmp_path / "plot_settings.json",
    )

    assert window.properties_tabs.count() == 2
    assert window.properties_tabs.tabText(0) == "Curve"
    assert window.properties_tabs.tabText(1) == "Plot"
    window.plot_title.setText("Load comparison")
    window.plot_x_label.setText("Time [s]")
    window.plot_primary_y_label.setText("Force [N]")
    window.plot_secondary_y_label.setText("Velocity [m/s]")
    window.plot_grid.setChecked(False)
    window.plot_legend.setChecked(False)
    window.plot_grid_alpha.setValue(0.4)
    window.plot_line_width.setValue(2.5)
    window.plot_x_tick_count.setValue(8)
    window.plot_minor_tick_count.setValue(2)
    window.plot_tick_font_size.setValue(12)
    window.plot_title_font_size.setValue(18)
    window.plot_secondary_y_axis.setChecked(False)
    window.plot_x_auto_range.setChecked(False)
    window.plot_range_inputs["x_min"].setValue(-1)
    window.plot_range_inputs["x_max"].setValue(3)
    window.plot_primary_y_auto_range.setChecked(False)
    window.plot_range_inputs["primary_y_min"].setValue(0)
    window.plot_range_inputs["primary_y_max"].setValue(5)
    window._pending_plot_background = "#20242b"
    window._pending_plot_foreground = "#f3f4f6"

    window._apply_plot_settings()

    assert window.project.plot_config["title"] == "Load comparison"
    assert window.project.plot_config["x_label"] == "Time [s]"
    assert window.project.plot_config["background"] == "#20242b"
    assert window.project.plot_config["grid"] is False
    assert window.project.plot_config["legend"] is False
    assert window.project.plot_config["x_tick_count"] == 8
    assert window.project.plot_config["minor_tick_count"] == 2
    assert window.project.plot_config["tick_font_size"] == 12
    assert window.project.plot_config["secondary_y_axis_visible"] is False
    assert window.project.plot_config["x_auto_range"] is False
    assert window.plot.legend.isVisible() is False
    assert window.plot.plot_item.getAxis("right").isVisible() is False
    assert window.plot.plot_item.vb.viewRange()[0] == pytest.approx([-1, 3])
    assert window.plot.plot_item.vb.viewRange()[1] == pytest.approx([0, 5])
    assert len(window.plot.plot_item.getAxis("bottom")._tickSpacing) == 2
    assert window.plot._items[0][0].opts["pen"].widthF() == 2.5

    second_path = tmp_path / "second.csv"
    second_path.write_text("t,value\n0,5\n1,6\n", encoding="utf-8")
    window._source_loaded(DataSourceLoader().load(second_path))
    assert window.plot_title.text() == "Load comparison"
    assert window.project.plot_config["title"] == "Load comparison"

    window._copy_plot_to_clipboard()
    assert not QApplication.clipboard().image().isNull()

    window._reset_plot_settings()

    assert window.project.plot_config == default_plot_config()


def test_manual_plot_range_rejects_reversed_limits(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    errors: list[str] = []
    monkeypatch.setattr(window, "_error", errors.append)
    original = dict(window.project.plot_config)
    window.plot_x_auto_range.setChecked(False)
    window.plot_range_inputs["x_min"].setValue(5)
    window.plot_range_inputs["x_max"].setValue(1)

    window._apply_plot_settings()

    assert errors == ["X minimum must be smaller than maximum."]
    assert window.project.plot_config == original
