from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph.exporters import ImageExporter, SVGExporter

from fileplotter.exporters import export_curves_csv
from fileplotter.importers import DataSourceLoader, ImportFailure
from fileplotter.models import (
    Curve,
    DataSource,
    Project,
    Transform,
    default_plot_config,
    stable_curve_id,
)
from fileplotter.project_io import ProjectFormatError, load_project, save_project
from fileplotter.plot_settings import load_plot_settings, save_plot_settings


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


class YSignalSelector(QToolButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self._update_text()

    def configure(
        self,
        options: list[tuple[str, str]],
        selected: set[str],
        on_toggle: Any,
    ) -> None:
        self._menu.clear()
        for label, column_id in options:
            action = self._menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(column_id in selected)
            action.toggled.connect(
                lambda checked, cid=column_id: self._toggle(
                    cid, checked, on_toggle
                )
            )
        self._update_text()

    def _toggle(self, column_id: str, checked: bool, callback: Any) -> None:
        callback(column_id, checked)
        self._update_text()

    def _update_text(self) -> None:
        selected = [action.text() for action in self._menu.actions() if action.isChecked()]
        if not selected:
            self.setText("Choose Y signals…")
        elif len(selected) == 1:
            self.setText(selected[0])
        else:
            self.setText(f"{len(selected)} Y signals selected")


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
        self._tick_counts = (6, 6, 6)
        self._minor_tick_count = 4
        self.plot_item.vb.sigResized.connect(self._sync_secondary)
        self.plot_item.vb.sigRangeChanged.connect(self._update_tick_spacing)
        self.secondary.sigRangeChanged.connect(self._update_tick_spacing)
        self.scene().sigMouseMoved.connect(self._mouse_moved)
        self.apply_config(default_plot_config())
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
        self.apply_config(project.plot_config)
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
            line_width = max(0.1, float(project.plot_config.get("line_width", 1.6)))
            pen = pg.mkPen(
                QColor(curve.color),
                width=line_width,
                style=PEN_STYLES[curve.line_style],
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
        self._apply_ranges(project.plot_config)
        self._update_tick_spacing()

    def apply_config(self, raw_config: dict[str, Any]) -> None:
        config = default_plot_config()
        config.update(raw_config)
        background = QColor(str(config["background"]))
        if not background.isValid():
            background = QColor(default_plot_config()["background"])
        foreground = QColor(str(config["foreground"]))
        if not foreground.isValid():
            foreground = QColor(default_plot_config()["foreground"])
        self.setBackground(background)
        alpha = min(1.0, max(0.0, float(config["grid_alpha"])))
        show_grid = bool(config["grid"])
        self.plot_item.showGrid(x=show_grid, y=show_grid, alpha=alpha)
        title_size = max(6.0, float(config["title_font_size"]))
        label_size = max(6.0, float(config["axis_label_font_size"]))
        tick_size = max(6.0, float(config["tick_font_size"]))
        self.plot_item.setTitle(
            str(config["title"]), color=foreground.name(), size=f"{title_size:g}pt"
        )
        label_style = {"color": foreground.name(), "font-size": f"{label_size:g}pt"}
        self.plot_item.setLabel("bottom", str(config["x_label"]), **label_style)
        self.plot_item.setLabel("left", str(config["primary_y_label"]), **label_style)
        self.plot_item.getAxis("right").setLabel(
            str(config["secondary_y_label"]), **label_style
        )
        self.plot_item.showAxis(
            "right", show=bool(config["secondary_y_axis_visible"])
        )
        tick_font = QFont()
        tick_font.setPointSizeF(tick_size)
        tick_length = int(config["tick_length"])
        for name in ("bottom", "left", "right"):
            axis = self.plot_item.getAxis(name)
            axis.setPen(foreground)
            axis.setTextPen(foreground)
            axis.setStyle(tickFont=tick_font, tickLength=tick_length)
        self._tick_counts = (
            max(2, int(config["x_tick_count"])),
            max(2, int(config["primary_y_tick_count"])),
            max(2, int(config["secondary_y_tick_count"])),
        )
        self._minor_tick_count = max(0, int(config["minor_tick_count"]))
        self._update_tick_spacing()
        self.legend.setLabelTextSize(f"{max(6.0, float(config['legend_font_size'])):g}pt")
        self.legend.setVisible(bool(config["legend"]))

    def _update_tick_spacing(self, *_args: Any) -> None:
        primary_range = self.plot_item.vb.viewRange()
        secondary_range = self.secondary.viewRange()
        for name, limits, count in (
            ("bottom", primary_range[0], self._tick_counts[0]),
            ("left", primary_range[1], self._tick_counts[1]),
            ("right", secondary_range[1], self._tick_counts[2]),
        ):
            span = abs(float(limits[1]) - float(limits[0]))
            axis = self.plot_item.getAxis(name)
            if not math.isfinite(span) or span <= 0:
                axis.setTickSpacing()
                continue
            major = span / max(1, count - 1)
            levels = [(major, 0.0)]
            if self._minor_tick_count:
                levels.append((major / (self._minor_tick_count + 1), 0.0))
            axis.setTickSpacing(levels=levels)

    def _apply_ranges(self, raw_config: dict[str, Any]) -> None:
        config = default_plot_config()
        config.update(raw_config)
        primary = self.plot_item.vb
        primary.enableAutoRange(
            axis=primary.XAxis, enable=bool(config["x_auto_range"])
        )
        primary.enableAutoRange(
            axis=primary.YAxis, enable=bool(config["primary_y_auto_range"])
        )
        self.secondary.enableAutoRange(
            axis=self.secondary.YAxis,
            enable=bool(config["secondary_y_auto_range"]),
        )
        if not config["x_auto_range"]:
            primary.setXRange(float(config["x_min"]), float(config["x_max"]), padding=0)
        if not config["primary_y_auto_range"]:
            primary.setYRange(
                float(config["primary_y_min"]),
                float(config["primary_y_max"]),
                padding=0,
            )
        if not config["secondary_y_auto_range"]:
            self.secondary.setYRange(
                float(config["secondary_y_min"]),
                float(config["secondary_y_max"]),
                padding=0,
            )
        primary.updateAutoRange()
        self.secondary.updateAutoRange()

    def auto_fit(self) -> None:
        self.plot_item.enableAutoRange()
        self.secondary.enableAutoRange()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FilePlotter")
        self.resize(1440, 860)
        self.loader = DataSourceLoader()
        app_plot_config = load_plot_settings()
        # A title belongs to the loaded data/project, not to global style defaults.
        app_plot_config["title"] = ""
        self.project = Project(plot_config=app_plot_config)
        self.project_path: Path | None = None
        self._jobs: list[tuple[QThread, ImportWorker, QProgressDialog]] = []
        self._dirty_transform_fields: set[str] = set()
        self._updating_controls = False
        self._source_x_selectors: dict[str, QComboBox] = {}
        self._source_y_selectors: dict[str, YSignalSelector] = {}
        self._curve_items: dict[tuple[str, str], QTreeWidgetItem] = {}
        self._build_ui()
        self._build_actions()
        self.statusBar().showMessage("Ready — add a CSV or XLSX source")

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Sources and Y signals", "Selection / status"])
        self.source_tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
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

        self.properties_tabs = QTabWidget()
        right = self.properties_tabs
        curve_tab = QWidget()
        right.addTab(curve_tab, "Curve")
        right_layout = QVBoxLayout(curve_tab)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(QLabel("Selected curve properties"))
        form = QFormLayout()
        self.axis = QComboBox()
        self.axis.addItems(["primary", "secondary"])
        self.line_style = QComboBox()
        self.line_style.addItems(["solid", "dash", "dot", "dashdot"])
        self.color_button = QPushButton("Choose…")
        self.color_button.clicked.connect(self._choose_color)
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

        plot_tab_page = QWidget()
        right.addTab(plot_tab_page, "Plot")
        plot_page_layout = QVBoxLayout(plot_tab_page)
        plot_page_layout.setContentsMargins(0, 0, 0, 0)
        plot_scroll = QScrollArea()
        plot_scroll.setWidgetResizable(True)
        plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        plot_page_layout.addWidget(plot_scroll)
        plot_tab = QWidget()
        plot_scroll.setWidget(plot_tab)
        plot_layout = QVBoxLayout(plot_tab)
        plot_layout.setContentsMargins(10, 10, 10, 10)
        plot_layout.addWidget(QLabel("Plot appearance"))
        plot_form = QFormLayout()
        plot_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        plot_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.plot_title = QLineEdit()
        self.plot_x_label = QLineEdit()
        self.plot_primary_y_label = QLineEdit()
        self.plot_secondary_y_label = QLineEdit()
        self.plot_background_button = QPushButton("Choose…")
        self.plot_background_button.clicked.connect(self._choose_plot_background)
        self.plot_foreground_button = QPushButton("Choose…")
        self.plot_foreground_button.clicked.connect(self._choose_plot_foreground)
        self.plot_grid = QCheckBox("Show grid")
        self.plot_legend = QCheckBox("Show legend")
        self.plot_secondary_y_axis = QCheckBox("Show secondary Y axis")
        self.plot_grid_alpha = QDoubleSpinBox()
        self.plot_grid_alpha.setRange(0.0, 1.0)
        self.plot_grid_alpha.setSingleStep(0.05)
        self.plot_grid_alpha.setDecimals(2)
        self.plot_line_width = QDoubleSpinBox()
        self.plot_line_width.setRange(0.5, 8.0)
        self.plot_line_width.setSingleStep(0.1)
        self.plot_line_width.setDecimals(1)
        self.plot_x_tick_count = QSpinBox()
        self.plot_primary_y_tick_count = QSpinBox()
        self.plot_secondary_y_tick_count = QSpinBox()
        for spin in (
            self.plot_x_tick_count,
            self.plot_primary_y_tick_count,
            self.plot_secondary_y_tick_count,
        ):
            spin.setRange(2, 20)
        self.plot_minor_tick_count = QSpinBox()
        self.plot_minor_tick_count.setRange(0, 10)
        self.plot_minor_tick_count.setSpecialValueText("None")
        self.plot_tick_font_size = QDoubleSpinBox()
        self.plot_axis_label_font_size = QDoubleSpinBox()
        self.plot_title_font_size = QDoubleSpinBox()
        self.plot_legend_font_size = QDoubleSpinBox()
        for spin in (
            self.plot_tick_font_size,
            self.plot_axis_label_font_size,
            self.plot_title_font_size,
            self.plot_legend_font_size,
        ):
            spin.setRange(6.0, 32.0)
            spin.setSingleStep(0.5)
            spin.setDecimals(1)
            spin.setSuffix(" pt")
        self.plot_tick_length = QSpinBox()
        self.plot_tick_length.setRange(-20, 20)
        self.plot_tick_length.setSuffix(" px")
        plot_form.addRow("Title", self.plot_title)
        plot_form.addRow("X axis label", self.plot_x_label)
        plot_form.addRow("Primary Y label", self.plot_primary_y_label)
        plot_form.addRow("Secondary Y label", self.plot_secondary_y_label)
        plot_form.addRow("Background", self.plot_background_button)
        plot_form.addRow("Axes and text color", self.plot_foreground_button)
        plot_form.addRow("Grid opacity", self.plot_grid_alpha)
        plot_form.addRow("Line width", self.plot_line_width)
        plot_form.addRow("X major ticks", self.plot_x_tick_count)
        plot_form.addRow("Primary Y major ticks", self.plot_primary_y_tick_count)
        plot_form.addRow("Secondary Y major ticks", self.plot_secondary_y_tick_count)
        plot_form.addRow("Minor ticks between majors", self.plot_minor_tick_count)
        plot_form.addRow("Tick font size", self.plot_tick_font_size)
        plot_form.addRow("Axis label size", self.plot_axis_label_font_size)
        plot_form.addRow("Title size", self.plot_title_font_size)
        plot_form.addRow("Legend size", self.plot_legend_font_size)
        plot_form.addRow("Tick length", self.plot_tick_length)
        plot_layout.addLayout(plot_form)
        plot_layout.addWidget(self.plot_grid)
        plot_layout.addWidget(self.plot_legend)
        plot_layout.addWidget(self.plot_secondary_y_axis)

        plot_layout.addWidget(QLabel("Axis ranges"))
        range_form = QFormLayout()
        range_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        range_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.plot_x_auto_range = QCheckBox("Auto X range")
        self.plot_primary_y_auto_range = QCheckBox("Auto primary Y range")
        self.plot_secondary_y_auto_range = QCheckBox("Auto secondary Y range")
        self.plot_range_inputs: dict[str, QDoubleSpinBox] = {}
        for key in (
            "x_min",
            "x_max",
            "primary_y_min",
            "primary_y_max",
            "secondary_y_min",
            "secondary_y_max",
        ):
            spin = QDoubleSpinBox()
            spin.setRange(-1e100, 1e100)
            spin.setDecimals(8)
            spin.setKeyboardTracking(False)
            self.plot_range_inputs[key] = spin
        range_form.addRow(self.plot_x_auto_range)
        range_form.addRow("X minimum", self.plot_range_inputs["x_min"])
        range_form.addRow("X maximum", self.plot_range_inputs["x_max"])
        range_form.addRow(self.plot_primary_y_auto_range)
        range_form.addRow(
            "Primary Y minimum", self.plot_range_inputs["primary_y_min"]
        )
        range_form.addRow(
            "Primary Y maximum", self.plot_range_inputs["primary_y_max"]
        )
        range_form.addRow(self.plot_secondary_y_auto_range)
        range_form.addRow(
            "Secondary Y minimum", self.plot_range_inputs["secondary_y_min"]
        )
        range_form.addRow(
            "Secondary Y maximum", self.plot_range_inputs["secondary_y_max"]
        )
        plot_layout.addLayout(range_form)
        for checkbox in (
            self.plot_x_auto_range,
            self.plot_primary_y_auto_range,
            self.plot_secondary_y_auto_range,
        ):
            checkbox.toggled.connect(self._update_range_control_states)
        apply_plot = QPushButton("Apply plot settings")
        apply_plot.clicked.connect(self._apply_plot_settings)
        reset_plot = QPushButton("Reset plot settings")
        reset_plot.clicked.connect(self._reset_plot_settings)
        copy_plot = QPushButton("Copy plot to clipboard")
        copy_plot.clicked.connect(self._copy_plot_to_clipboard)
        plot_layout.addStretch(1)
        plot_page_layout.addWidget(apply_plot)
        plot_page_layout.addWidget(reset_plot)
        plot_page_layout.addWidget(copy_plot)

        self.axis.currentTextChanged.connect(self._apply_axis)
        self.line_style.currentTextChanged.connect(self._apply_line_style)
        self._load_plot_controls()

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
            ("Copy plot to clipboard", "Ctrl+Shift+C", self._copy_plot_to_clipboard),
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
        if not str(self.project.plot_config.get("title", "")).strip():
            self.project.plot_config["title"] = source.path.name
            self._load_plot_controls()
            self.plot.render_project(self.project)
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
        self._source_x_selectors.clear()
        self._source_y_selectors.clear()
        self._curve_items.clear()
        for source in self.project.sources.values():
            root = QTreeWidgetItem([source.display_name, "ready" if source.available else "missing"])
            root.setData(0, Qt.ItemDataRole.UserRole, ("source", source.source_id))
            self.source_tree.addTopLevelItem(root)
            numeric = source.numeric_columns
            if not numeric:
                continue
            mapping_group = QTreeWidgetItem(["Axis mapping", ""])
            root.addChild(mapping_group)
            x_row = QTreeWidgetItem(["X axis", ""])
            mapping_group.addChild(x_row)
            x_combo = QComboBox()
            for column in numeric:
                x_combo.addItem(self._column_label(source, column.column_id), column.column_id)
            existing = next(
                (curve for curve in self.project.curves.values() if curve.source_id == source.source_id),
                None,
            )
            selected_x = self.project.source_x_columns.get(source.source_id)
            if not selected_x and existing:
                selected_x = existing.x_column_id
            if selected_x:
                x_combo.setCurrentIndex(max(0, x_combo.findData(selected_x)))
            self.project.source_x_columns[source.source_id] = str(x_combo.currentData())
            for curve in self.project.curves.values():
                if curve.source_id == source.source_id:
                    curve.x_column_id = str(x_combo.currentData())
                    if curve.y_column_id == x_combo.currentData():
                        curve.visible = False
            x_combo.currentIndexChanged.connect(
                lambda _index, sid=source.source_id, combo=x_combo: self._set_source_x(
                    sid, combo.currentData()
                )
            )
            self.source_tree.setItemWidget(x_row, 1, x_combo)
            self._source_x_selectors[source.source_id] = x_combo

            y_row = QTreeWidgetItem(["Y signals", ""])
            mapping_group.addChild(y_row)
            y_selector = YSignalSelector()
            selected_y = {
                curve.y_column_id
                for curve in self.project.curves.values()
                if curve.source_id == source.source_id and curve.visible
            }
            y_selector.configure(
                [
                    (self._column_label(source, column.column_id), column.column_id)
                    for column in numeric
                    if column.column_id != x_combo.currentData()
                ],
                selected_y,
                lambda column_id, checked, sid=source.source_id: self._set_source_y(
                    sid, column_id, checked
                ),
            )
            self.source_tree.setItemWidget(y_row, 1, y_selector)
            self._source_y_selectors[source.source_id] = y_selector

            signals_group = QTreeWidgetItem(["Available signals", ""])
            root.addChild(signals_group)
            for column in numeric:
                curve_id = stable_curve_id(source.source_id, column.column_id)
                curve = self.project.curves.get(curve_id)
                item = QTreeWidgetItem(
                    [
                        self._column_label(source, column.column_id),
                        self._curve_status(column, curve),
                    ]
                )
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("curve", source.source_id, column.column_id),
                )
                signals_group.addChild(item)
                self._curve_items[(source.source_id, column.column_id)] = item
            root.setExpanded(True)
            mapping_group.setExpanded(True)
            signals_group.setExpanded(True)
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

    def _curve_status(self, column: Any, curve: Curve | None) -> str:
        prefix = "plotted" if curve and curve.visible else "available"
        quality = self._quality_text(column)
        return f"{prefix} · {quality}"

    def _set_source_y(
        self, source_id: str, y_column_id: str, visible: bool
    ) -> None:
        curve_id = stable_curve_id(source_id, y_column_id)
        curve = self.project.curves.get(curve_id)
        if curve is None:
            source = self.project.sources[source_id]
            curve = Curve(
                source_id=source_id,
                x_column_id=self.project.source_x_columns[source_id],
                y_column_id=y_column_id,
                visible=visible,
                display_label=f"{source.display_name} · {self._column_label(source, y_column_id)}",
                color=PALETTE[len(self.project.curves) % len(PALETTE)],
            )
            self.project.curves[curve_id] = curve
        else:
            curve.visible = visible
            curve.x_column_id = self.project.source_x_columns[source_id]
        source = self.project.sources[source_id]
        column = next(col for col in source.columns if col.column_id == y_column_id)
        item = self._curve_items.get((source_id, y_column_id))
        if item is not None:
            item.setText(1, self._curve_status(column, curve))
        self.plot.render_project(self.project)

    def _set_source_x(self, source_id: str, column_id: str) -> None:
        if not column_id:
            return
        self.project.source_x_columns[source_id] = column_id
        for curve in self.project.curves.values():
            if curve.source_id == source_id:
                curve.x_column_id = column_id
                if curve.y_column_id == column_id:
                    curve.visible = False
        source = self.project.sources[source_id]
        selected_y = {
            curve.y_column_id
            for curve in self.project.curves.values()
            if curve.source_id == source_id and curve.visible
        }
        selector = self._source_y_selectors[source_id]
        selector.configure(
            [
                (self._column_label(source, column.column_id), column.column_id)
                for column in source.numeric_columns
                if column.column_id != column_id
            ],
            selected_y,
            lambda y_column_id, checked, sid=source_id: self._set_source_y(
                sid, y_column_id, checked
            ),
        )
        for column in source.numeric_columns:
            item = self._curve_items.get((source_id, column.column_id))
            curve = self.project.curves.get(stable_curve_id(source_id, column.column_id))
            if item is not None:
                item.setText(1, self._curve_status(column, curve))
        self.plot.render_project(self.project)

    def _selected_curves(self) -> list[Curve]:
        selected: list[Curve] = []
        for item in self.source_tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "curve":
                curve = self.project.curves.get(stable_curve_id(data[1], data[2]))
                if curve and curve.visible:
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
        self._updating_controls = True
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

    def _load_plot_controls(self) -> None:
        config = default_plot_config()
        config.update(self.project.plot_config)
        self.plot_title.setText(str(config["title"]))
        self.plot_x_label.setText(str(config["x_label"]))
        self.plot_primary_y_label.setText(str(config["primary_y_label"]))
        self.plot_secondary_y_label.setText(str(config["secondary_y_label"]))
        self.plot_grid.setChecked(bool(config["grid"]))
        self.plot_legend.setChecked(bool(config["legend"]))
        self.plot_grid_alpha.setValue(float(config["grid_alpha"]))
        self.plot_line_width.setValue(float(config["line_width"]))
        self.plot_x_tick_count.setValue(int(config["x_tick_count"]))
        self.plot_primary_y_tick_count.setValue(int(config["primary_y_tick_count"]))
        self.plot_secondary_y_tick_count.setValue(int(config["secondary_y_tick_count"]))
        self.plot_minor_tick_count.setValue(int(config["minor_tick_count"]))
        self.plot_tick_font_size.setValue(float(config["tick_font_size"]))
        self.plot_axis_label_font_size.setValue(
            float(config["axis_label_font_size"])
        )
        self.plot_title_font_size.setValue(float(config["title_font_size"]))
        self.plot_legend_font_size.setValue(float(config["legend_font_size"]))
        self.plot_tick_length.setValue(int(config["tick_length"]))
        self.plot_secondary_y_axis.setChecked(
            bool(config["secondary_y_axis_visible"])
        )
        self.plot_x_auto_range.setChecked(bool(config["x_auto_range"]))
        self.plot_primary_y_auto_range.setChecked(
            bool(config["primary_y_auto_range"])
        )
        self.plot_secondary_y_auto_range.setChecked(
            bool(config["secondary_y_auto_range"])
        )
        for key, spin in self.plot_range_inputs.items():
            spin.setValue(float(config[key]))
        self._update_range_control_states()
        self._pending_plot_background = str(config["background"])
        self._pending_plot_foreground = str(config["foreground"])
        self.plot_background_button.setStyleSheet(
            f"background: {self._pending_plot_background};"
        )
        self.plot_foreground_button.setStyleSheet(
            f"background: {self._pending_plot_foreground};"
        )

    def _update_range_control_states(self, _checked: bool | None = None) -> None:
        for prefix, automatic in (
            ("x", self.plot_x_auto_range.isChecked()),
            ("primary_y", self.plot_primary_y_auto_range.isChecked()),
            ("secondary_y", self.plot_secondary_y_auto_range.isChecked()),
        ):
            self.plot_range_inputs[f"{prefix}_min"].setEnabled(not automatic)
            self.plot_range_inputs[f"{prefix}_max"].setEnabled(not automatic)

    def _manual_ranges_are_valid(self) -> bool:
        for label, prefix, automatic in (
            ("X", "x", self.plot_x_auto_range.isChecked()),
            ("Primary Y", "primary_y", self.plot_primary_y_auto_range.isChecked()),
            ("Secondary Y", "secondary_y", self.plot_secondary_y_auto_range.isChecked()),
        ):
            if automatic:
                continue
            minimum = self.plot_range_inputs[f"{prefix}_min"].value()
            maximum = self.plot_range_inputs[f"{prefix}_max"].value()
            if minimum >= maximum:
                self._error(f"{label} minimum must be smaller than maximum.")
                return False
        return True

    def _choose_plot_background(self) -> None:
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(
            QColor(self._pending_plot_background), self, "Plot background"
        )
        if not color.isValid():
            return
        self._pending_plot_background = color.name()
        self.plot_background_button.setStyleSheet(
            f"background: {self._pending_plot_background};"
        )

    def _choose_plot_foreground(self) -> None:
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(
            QColor(self._pending_plot_foreground), self, "Axes and text color"
        )
        if not color.isValid():
            return
        self._pending_plot_foreground = color.name()
        self.plot_foreground_button.setStyleSheet(
            f"background: {self._pending_plot_foreground};"
        )

    def _apply_plot_settings(self) -> None:
        if not self._manual_ranges_are_valid():
            return
        self.project.plot_config.update(
            {
                "title": self.plot_title.text().strip(),
                "x_label": self.plot_x_label.text().strip(),
                "primary_y_label": self.plot_primary_y_label.text().strip(),
                "secondary_y_label": self.plot_secondary_y_label.text().strip(),
                "background": self._pending_plot_background,
                "foreground": self._pending_plot_foreground,
                "grid": self.plot_grid.isChecked(),
                "grid_alpha": self.plot_grid_alpha.value(),
                "legend": self.plot_legend.isChecked(),
                "line_width": self.plot_line_width.value(),
                "x_tick_count": self.plot_x_tick_count.value(),
                "primary_y_tick_count": self.plot_primary_y_tick_count.value(),
                "secondary_y_tick_count": self.plot_secondary_y_tick_count.value(),
                "minor_tick_count": self.plot_minor_tick_count.value(),
                "tick_font_size": self.plot_tick_font_size.value(),
                "axis_label_font_size": self.plot_axis_label_font_size.value(),
                "title_font_size": self.plot_title_font_size.value(),
                "legend_font_size": self.plot_legend_font_size.value(),
                "tick_length": self.plot_tick_length.value(),
                "secondary_y_axis_visible": self.plot_secondary_y_axis.isChecked(),
                "x_auto_range": self.plot_x_auto_range.isChecked(),
                "x_min": self.plot_range_inputs["x_min"].value(),
                "x_max": self.plot_range_inputs["x_max"].value(),
                "primary_y_auto_range": self.plot_primary_y_auto_range.isChecked(),
                "primary_y_min": self.plot_range_inputs["primary_y_min"].value(),
                "primary_y_max": self.plot_range_inputs["primary_y_max"].value(),
                "secondary_y_auto_range": self.plot_secondary_y_auto_range.isChecked(),
                "secondary_y_min": self.plot_range_inputs["secondary_y_min"].value(),
                "secondary_y_max": self.plot_range_inputs["secondary_y_max"].value(),
            }
        )
        self.plot.render_project(self.project)
        try:
            path = save_plot_settings(self.project.plot_config)
        except OSError as exc:
            self.statusBar().showMessage(
                f"Plot updated, but settings could not be saved: {exc}", 8000
            )
        else:
            self.statusBar().showMessage(f"Plot settings saved to {path.name}", 5000)

    def _reset_plot_settings(self) -> None:
        self.project.plot_config = default_plot_config()
        self._load_plot_controls()
        self.plot.render_project(self.project)
        try:
            save_plot_settings(self.project.plot_config)
        except OSError as exc:
            self.statusBar().showMessage(
                f"Plot reset, but settings could not be saved: {exc}", 8000
            )
        else:
            self.statusBar().showMessage("Plot settings reset and saved", 3000)

    def _copy_plot_to_clipboard(self) -> None:
        try:
            exporter = ImageExporter(self.plot.plot_item)
            exporter.parameters()["width"] = 2400
            exporter.export(copy=True)
            self.statusBar().showMessage("Plot copied to clipboard", 3000)
        except Exception as exc:
            self._error(f"Could not copy plot: {exc}")

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
        self._load_plot_controls()
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
            window._load_plot_controls()
            window.plot.render_project(project)
            if warnings:
                window.statusBar().showMessage("; ".join(warnings), 15_000)
        except (ProjectFormatError, OSError) as exc:
            QMessageBox.critical(window, "FilePlotter", str(exc))
    return app.exec()
