from pathlib import Path
from dataclasses import replace

from PyQt6.QtCore import Qt

from fileplotter.app import MainWindow
from fileplotter.importers import DataSourceLoader
from fileplotter.models import default_plot_config


def test_source_tree_checkbox_creates_curve_and_plot(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,signal\n0,2\n1,4\n", encoding="utf-8")
    source = DataSourceLoader().load(path)
    window = MainWindow()
    qtbot.addWidget(window)

    window._source_loaded(source)
    signal_item = window.source_tree.topLevelItem(0).child(2)
    signal_item.setCheckState(0, Qt.CheckState.Checked)

    assert len(window.project.curves) == 1
    assert len(window.plot._items) == 1


def test_batch_transform_preserves_unedited_values_and_reset(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,a,b\n0,2,3\n1,4,5\n", encoding="utf-8")
    source = DataSourceLoader().load(path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._source_loaded(source)
    root = window.source_tree.topLevelItem(0)
    first_item, second_item = root.child(2), root.child(3)
    first_item.setCheckState(0, Qt.CheckState.Checked)
    second_item.setCheckState(0, Qt.CheckState.Checked)
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


def test_plot_customization_tab_applies_and_resets_settings(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "signals.csv"
    path.write_text("t,signal\n0,2\n1,4\n", encoding="utf-8")
    window = MainWindow()
    qtbot.addWidget(window)
    window._source_loaded(DataSourceLoader().load(path))
    signal_item = window.source_tree.topLevelItem(0).child(2)
    signal_item.setCheckState(0, Qt.CheckState.Checked)

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
    window._pending_plot_background = "#20242b"

    window._apply_plot_settings()

    assert window.project.plot_config["title"] == "Load comparison"
    assert window.project.plot_config["x_label"] == "Time [s]"
    assert window.project.plot_config["background"] == "#20242b"
    assert window.project.plot_config["grid"] is False
    assert window.project.plot_config["legend"] is False
    assert window.plot.legend.isVisible() is False
    assert window.plot._items[0][0].opts["pen"].widthF() == 2.5

    window._reset_plot_settings()

    assert window.project.plot_config == default_plot_config()
