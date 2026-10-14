from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph.exporters import ImageExporter, SVGExporter

from fileplotter.exporters import export_curves_csv
from fileplotter.importers import DataSourceLoader, ImportFailure
from fileplotter.models import Curve, DataSource, Project, Transform, stable_curve_id
from fileplotter.project_io import ProjectFormatError, load_project, save_project


PALETTE = [
    "#60a5fa",
    "#f97316",
    "#34d399",
    "#f472b6",
    "#facc15",
    "#a78bfa",
    "#22d3ee",
    "#fb7185",
]
PEN_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
}


class ImportWorker(QObject):
    progress = pyqtSignal(int, str)
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self, loader: DataSourceLoader, path: str, sheet: str | None, header_row: int
    ) -> None:
        super().__init__()
        self.loader = loader
        self.path = path
        self.sheet = sheet
        self.header_row = header_row

    @pyqtSlot()
    def run(self) -> None:
        try:
            source = self.loader.load(
                self.path,
                sheet=self.sheet,
                header_row=self.header_row,
                progress=self.progress.emit,
            )
            self.loaded.emit(source)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class PlotCanvas(pg.PlotWidget):
    cursor_text = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setBackground("#111827")
        self.plot_item = self.getPlotItem()
        self.plot_item.showGrid(x=True, y=True, alpha=0.25)
        self.plot_item.setLabel("bottom", "X")
        self.plot_item.setLabel("left", "Primary Y")
        self.plot_item.showAxis("right")
        self.plot_item.getAxis("right").setLabel("Secondary Y")
        self.secondary = pg.ViewBox()
        self.plot_item.scene().addItem(self.secondary)
        self.plot_item.getAxis("right").linkToView(self.secondary)
        self.secondary.setXLink(self.plot_item)
        self.legend = self.plot_item.addLegend(offset=(12, 12))
        self._items: list[tuple[pg.PlotDataItem, str]] = []
        self.plot_item.vb.sigResized.connect(self._sync_secondary)
        self.scene().sigMouseMoved.connect(self._mouse_moved)
        self._sync_secondary()

    def _sync_secondary(self) -> None:
        self.secondary.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.secondary.linkedViewChanged(
            self.plot_item.vb, self.secondary.XAxis
        )

    def _mouse_moved(self, position: Any) -> None:
        if self.plot_item.sceneBoundingRect().contains(position):
            point = self.plot_item.vb.mapSceneToView(position)
            self.cursor_text.emit(f"Cursor  X {point.x():.7g}   Y {point.y():.7g}")

    def render_project(self, project: Project) -> None:
        for item, axis in self._items:
            (self.secondary if axis == "secondary" else self.plot_item).removeItem(item)
        self._items.clear()
        self.legend.clear()
        for curve in project.curves.values():
            source = project.sources.get(curve.source_id)
            if not curve.visible or not source or not source.available:
                continue
            try:
                x, y = project.curve_arrays(curve)
            except KeyError:
                continue
            pen = pg.mkPen(
                QColor(curve.color), width=1.6, style=PEN_STYLES[curve.line_style]
            )
            item = pg.PlotDataItem(x, y, pen=pen, connect="finite")
            if curve.axis == "secondary":
                self.secondary.addItem(item)
            else:
                self.plot_item.addItem(item)
            # Clipping queries the owning ViewBox in pyqtgraph 0.14, so enable
            # it only after the item has been attached to its final view.
            item.setDownsampling(auto=True, method="peak")
            item.setClipToView(True)
            self.legend.addItem(item, curve.display_label)
            self._items.append((item, curve.axis))

    def auto_fit(self) -> None:
        self.plot_item.enableAutoRange()
        self.secondary.enableAutoRange()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FilePlotter")
        self.resize(1440, 860)
        self.loader = DataSourceLoader()
        self.project = Project()
        self.project_path: Path | None = None
        self._jobs: list[tuple[QThread, ImportWorker, QProgressDialog]] = []
        self._dirty_transform_fields: set[str] = set()
        self._updating_controls = False
        self._build_ui()
        self._build_actions()
        self.statusBar().showMessage("Ready — add a CSV or XLSX source")

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Sources and signals", "Status"])
        self.source_tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        self.source_tree.itemChanged.connect(self._tree_item_changed)
        self.source_tree.itemSelectionChanged.connect(self._selection_changed)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        add_source = QPushButton("Add CSV / XLSX")
        add_source.clicked.connect(self._choose_sources)
        left_layout.addWidget(add_source)
        left_layout.addWidget(self.source_tree)

        self.plot = PlotCanvas()
        self.plot.cursor_text.connect(self.statusBar().showMessage)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(QLabel("Selected curve properties"))
        form = QFormLayout()
        self.x_column = QComboBox()
        self.axis = QComboBox()
        self.axis.addItems(["primary", "secondary"])
        self.line_style = QComboBox()
        self.line_style.addItems(["solid", "dash", "dot", "dashdot"])
        self.color_button = QPushButton("Choose…")
        self.color_button.clicked.connect(self._choose_color)
        form.addRow("X column", self.x_column)
        form.addRow("Y axis", self.axis)
        form.addRow("Line style", self.line_style)
        form.addRow("Color", self.color_button)
        self.transform_inputs: dict[str, QDoubleSpinBox] = {}
        for key, label, default in (
            ("x_scale", "X scale", 1.0),
            ("x_shift", "X shift", 0.0),
            ("y_scale", "Y scale", 1.0),
            ("y_shift", "Y shift", 0.0),
        ):
            spin = QDoubleSpinBox()
            spin.setRange(-1e100, 1e100)
            spin.setDecimals(10)
            spin.setValue(default)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(
                lambda _value, name=key: self._mark_transform_dirty(name)
            )
            self.transform_inputs[key] = spin
            form.addRow(label, spin)
        right_layout.addLayout(form)

        apply_transform = QPushButton("Apply transform")
        apply_transform.clicked.connect(self._apply_transform)
        reset_transform = QPushButton("Reset transform")
        reset_transform.clicked.connect(self._reset_transform)
        fit_plot = QPushButton("Auto-fit plot")
        fit_plot.clicked.connect(self.plot.auto_fit)
        right_layout.addWidget(apply_transform)
        right_layout.addWidget(reset_transform)
        right_layout.addWidget(fit_plot)
        self.selection_summary = QLabel("Select one or more signal rows.")
        self.selection_summary.setWordWrap(True)
        right_layout.addWidget(self.selection_summary)
        right_layout.addStretch(1)

        self.x_column.currentIndexChanged.connect(self._apply_x_column)
        self.axis.currentTextChanged.connect(self._apply_axis)
        self.line_style.currentTextChanged.connect(self._apply_line_style)

        splitter.addWidget(left)
        splitter.addWidget(self.plot)
        splitter.addWidget(right)
        splitter.setSizes([330, 820, 290])
        self.setCentralWidget(splitter)

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        actions = [
            ("Add source…", "Ctrl+O", self._choose_sources),
            ("Open project…", "Ctrl+Shift+O", self._open_project),
            ("Save project", "Ctrl+S", self._save_project),
            ("Save project as…", "Ctrl+Shift+S", self._save_project_as),
            ("Export transformed CSV…", "Ctrl+E", self._export_data),
            ("Export plot…", "Ctrl+P", self._export_plot),
        ]
        for label, shortcut, slot in actions:
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _choose_sources(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add data sources",
            "",
            "Data files (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)",
        )
        for path in paths:
            sheet: str | None = None
            if Path(path).suffix.lower() == ".xlsx":
                try:
                    sheets = self.loader.workbook_sheets(path)
                except ImportFailure as exc:
                    self._error(str(exc))
                    continue
                sheet, accepted = QInputDialog.getItem(
                    self, "Worksheet", "Select worksheet", sheets, 0, False
                )
                if not accepted:
                    continue
            header_row_one_based, accepted = QInputDialog.getInt(
                self,
                "Header row",
                "Header row number (first row is 1)",
                1,
                1,
                1_000_000,
            )
            if accepted:
                self._start_import(path, sheet, header_row_one_based - 1)

    def _start_import(self, path: str, sheet: str | None, header_row: int) -> None:
        dialog = QProgressDialog("Preparing import…", "Hide", 0, 100, self)
        dialog.setWindowTitle(f"Importing {Path(path).name}")
        dialog.setAutoClose(False)
        dialog.setValue(0)
        thread = QThread(self)
        worker = ImportWorker(self.loader, path, sheet, header_row)
        worker.moveToThread(thread)
        worker.progress.connect(
            lambda value, message: (dialog.setLabelText(message), dialog.setValue(value))
        )
        worker.loaded.connect(self._source_loaded)
        worker.failed.connect(self._error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(dialog.close)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda thread=thread: self._jobs_finished(thread)
        )
        thread.started.connect(worker.run)
        self._jobs.append((thread, worker, dialog))
        thread.start()
        dialog.show()

    def _jobs_finished(self, thread: QThread) -> None:
        self._jobs = [job for job in self._jobs if job[0] is not thread]

    @pyqtSlot(object)
    def _source_loaded(self, source: DataSource) -> None:
        self.project.sources[source.source_id] = source
        self._rebuild_tree()
        issues = sum(
            column.missing_count + column.invalid_count
            for column in source.numeric_columns
        )
        message = f"Loaded {source.display_name}: {len(source.numeric_columns)} numeric columns"
        if issues:
            message += f" ({issues:,} missing or invalid samples shown as gaps)"
        self.statusBar().showMessage(message, 10_000)

    def _rebuild_tree(self) -> None:
        self.source_tree.blockSignals(True)
        self.source_tree.clear()
        for source in self.project.sources.values():
            root = QTreeWidgetItem([source.display_name, "ready" if source.available else "missing"])
            root.setData(0, Qt.ItemDataRole.UserRole, ("source", source.source_id))
            self.source_tree.addTopLevelItem(root)
            numeric = source.numeric_columns
            if not numeric:
                continue
            x_row = QTreeWidgetItem(["X axis", ""])
            root.addChild(x_row)
            x_combo = QComboBox()
            for column in numeric:
                x_combo.addItem(self._column_label(source, column.column_id), column.column_id)
            existing = next(
                (curve for curve in self.project.curves.values() if curve.source_id == source.source_id),
                None,
            )
            if existing:
                x_combo.setCurrentIndex(max(0, x_combo.findData(existing.x_column_id)))
            x_combo.currentIndexChanged.connect(
                lambda _index, sid=source.source_id, combo=x_combo: self._set_source_x(
                    sid, combo.currentData()
                )
            )
            self.source_tree.setItemWidget(x_row, 1, x_combo)
            default_x = x_combo.currentData()
            for column in numeric:
                curve_id = stable_curve_id(source.source_id, column.column_id)
                curve = self.project.curves.get(curve_id)
                item = QTreeWidgetItem(
                    [self._column_label(source, column.column_id), self._quality_text(column)]
                )
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if curve and curve.visible
                    else Qt.CheckState.Unchecked,
                )
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("curve", source.source_id, column.column_id, default_x),
                )
                root.addChild(item)
            root.setExpanded(True)
        self.source_tree.blockSignals(False)

    def _column_label(self, source: DataSource, column_id: str) -> str:
        column = next(col for col in source.columns if col.column_id == column_id)
        duplicates = [col for col in source.columns if col.name == column.name]
        return (
            f"{column.name} [column {column.position + 1}]"
            if len(duplicates) > 1
            else column.name
        )

    @staticmethod
    def _quality_text(column: Any) -> str:
        count = column.missing_count + column.invalid_count
        return f"{count:,} gaps" if count else "numeric"

    def _tree_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "curve":
            return
        _, source_id, y_column_id, default_x = data
        curve_id = stable_curve_id(source_id, y_column_id)
        visible = item.checkState(0) == Qt.CheckState.Checked
        curve = self.project.curves.get(curve_id)
        if curve is None:
            source = self.project.sources[source_id]
            curve = Curve(
                source_id=source_id,
                x_column_id=default_x,
                y_column_id=y_column_id,
                visible=visible,
                display_label=f"{source.display_name} · {self._column_label(source, y_column_id)}",
                color=PALETTE[len(self.project.curves) % len(PALETTE)],
            )
            self.project.curves[curve_id] = curve
        else:
            curve.visible = visible
        self.plot.render_project(self.project)

    def _set_source_x(self, source_id: str, column_id: str) -> None:
        for curve in self.project.curves.values():
            if curve.source_id == source_id:
                curve.x_column_id = column_id
        self.plot.render_project(self.project)

    def _selected_curves(self) -> list[Curve]:
        selected: list[Curve] = []
        for item in self.source_tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "curve":
                curve = self.project.curves.get(stable_curve_id(data[1], data[2]))
                if curve:
                    selected.append(curve)
        return selected

    def _selection_changed(self) -> None:
        curves = self._selected_curves()
        self.selection_summary.setText(
            f"{len(curves)} curve{'s' if len(curves) != 1 else ''} selected"
            if curves
            else "Select a checked signal row to edit it."
        )
        if not curves:
            return
        first = curves[0]
        source = self.project.sources[first.source_id]
        self._updating_controls = True
        self.x_column.clear()
        for column in source.numeric_columns:
            self.x_column.addItem(self._column_label(source, column.column_id), column.column_id)
        self.x_column.setCurrentIndex(max(0, self.x_column.findData(first.x_column_id)))
        self.axis.setCurrentText(first.axis)
        self.line_style.setCurrentText(first.line_style)
        self.color_button.setStyleSheet(f"background: {first.color};")
        for key, spin in self.transform_inputs.items():
            spin.setValue(getattr(first.transform, key))
        self._dirty_transform_fields.clear()
        self._updating_controls = False

    def _mark_transform_dirty(self, field: str) -> None:
        if not self._updating_controls:
            self._dirty_transform_fields.add(field)

    def _apply_transform(self) -> None:
        curves = self._selected_curves()
        if not curves:
            self._error("Select at least one existing curve.")
            return
        fields = self._dirty_transform_fields or set(self.transform_inputs)
        updates = {key: self.transform_inputs[key].value() for key in fields}
        if any(key.endswith("scale") and value == 0 for key, value in updates.items()):
            answer = QMessageBox.warning(
                self,
                "Zero scale",
                "A zero scale collapses the corresponding axis. Apply it anyway?",
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Apply:
                return
        for curve in curves:
            curve.transform = replace(curve.transform, **updates)
        self._dirty_transform_fields.clear()
        self.plot.render_project(self.project)

    def _reset_transform(self) -> None:
        for curve in self._selected_curves():
            curve.transform = Transform()
        self._selection_changed()
        self.plot.render_project(self.project)

    def _apply_x_column(self) -> None:
        if self._updating_controls:
            return
        column_id = self.x_column.currentData()
        for curve in self._selected_curves():
            source = self.project.sources[curve.source_id]
            if any(col.column_id == column_id for col in source.numeric_columns):
                curve.x_column_id = column_id
        self.plot.render_project(self.project)

    def _apply_axis(self, axis: str) -> None:
        if self._updating_controls:
            return
        for curve in self._selected_curves():
            curve.axis = axis
        self.plot.render_project(self.project)

    def _apply_line_style(self, style: str) -> None:
        if self._updating_controls:
            return
        for curve in self._selected_curves():
            curve.line_style = style
        self.plot.render_project(self.project)

    def _choose_color(self) -> None:
        curves = self._selected_curves()
        if not curves:
            return
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor(curves[0].color), self, "Curve color")
        if not color.isValid():
            return
        for curve in curves:
            curve.color = color.name()
        self.color_button.setStyleSheet(f"background: {color.name()};")
        self.plot.render_project(self.project)

    def _save_project(self) -> None:
        if self.project_path is None:
            self._save_project_as()
            return
        try:
            save_project(self.project, self.project_path)
            self.statusBar().showMessage(f"Saved {self.project_path.name}", 5000)
        except OSError as exc:
            self._error(f"Could not save project: {exc}")

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", "", "FilePlotter project (*.fplot.json);;JSON (*.json)"
        )
        if path:
            self.project_path = Path(path)
            self._save_project()

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "FilePlotter project (*.fplot.json *.json)"
        )
        if not path:
            return

        def relink(descriptor: dict[str, Any]) -> str | None:
            answer = QMessageBox.question(
                self,
                "Missing source",
                f"Locate missing source?\n{descriptor['path']}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
            replacement, _ = QFileDialog.getOpenFileName(
                self, "Relink source", "", "Data files (*.csv *.xlsx)"
            )
            return replacement or None

        try:
            project, warnings = load_project(path, loader=self.loader, relink=relink)
        except (ProjectFormatError, OSError) as exc:
            self._error(str(exc))
            return
        self.project = project
        self.project_path = Path(path)
        self._rebuild_tree()
        self.plot.render_project(project)
        if warnings:
            QMessageBox.warning(self, "Project warnings", "\n".join(warnings))

    def _export_data(self) -> None:
        curves = self._selected_curves() or [
            curve for curve in self.project.curves.values() if curve.visible
        ]
        if not curves:
            self._error("Select or display at least one curve.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export transformed data", "", "CSV (*.csv)"
        )
        if path:
            try:
                export_curves_csv(self.project, [curve.curve_id for curve in curves], path)
                self.statusBar().showMessage(f"Exported {Path(path).name}", 5000)
            except (OSError, ValueError, KeyError) as exc:
                self._error(f"Could not export data: {exc}")

    def _export_plot(self) -> None:
        path, selected = QFileDialog.getSaveFileName(
            self, "Export plot", "", "PNG image (*.png);;SVG vector image (*.svg)"
        )
        if not path:
            return
        try:
            exporter = (
                SVGExporter(self.plot.plot_item)
                if "SVG" in selected or Path(path).suffix.lower() == ".svg"
                else ImageExporter(self.plot.plot_item)
            )
            if isinstance(exporter, ImageExporter):
                exporter.parameters()["width"] = 2400
            exporter.export(path)
            self.statusBar().showMessage(f"Exported {Path(path).name}", 5000)
        except Exception as exc:
            self._error(f"Could not export plot: {exc}")

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "FilePlotter", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._jobs:
            QMessageBox.information(
                self, "Import running", "Wait for active imports before closing."
            )
            event.ignore()
            return
        super().closeEvent(event)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-source CSV/XLSX signal plotter")
    parser.add_argument("project", nargs="?", help="Project file to open")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    pg.setConfigOptions(antialias=True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("FilePlotter")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    if arguments.project:
        try:
            project, warnings = load_project(arguments.project, loader=window.loader)
            window.project = project
            window.project_path = Path(arguments.project)
            window._rebuild_tree()
            window.plot.render_project(project)
            if warnings:
                window.statusBar().showMessage("; ".join(warnings), 15_000)
        except (ProjectFormatError, OSError) as exc:
            QMessageBox.critical(window, "FilePlotter", str(exc))
    return app.exec()
