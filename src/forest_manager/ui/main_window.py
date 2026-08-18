from __future__ import annotations

from pathlib import Path
from typing import Any

from forest_manager.site_model import SiteModelService, SiteViewerPresenter

from .controller import ForestManagerUIController, ForestUIState, PropertyRow
from .semantic_controls import artist_control_specs
from .project_viewer import ProjectViewerWidget

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QCheckBox,
        QDoubleSpinBox,
        QComboBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QSplitter,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QApplication = None


DOMAIN_TABS = (
    "All Properties",
    "Geometry",
    "Areas",
    "Distribution",
    "Transform",
    "Surface / Camera",
    "Material / Animation",
    "Display / Render / Effects",
)


def _format_value(value: Any) -> str:
    if value is None:
        return "<null>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_value(v) for v in value)
    return str(value)


def _trim_localized_decimal(text: str, decimal_point: str) -> str:
    if not decimal_point or decimal_point not in text:
        return text
    whole, fraction = text.rsplit(decimal_point, 1)
    fraction = fraction.rstrip("0")
    return whole if not fraction else whole + decimal_point + fraction


class CompactDoubleSpinBox(QDoubleSpinBox if QApplication is not None else object):
    def textFromValue(self, value: float) -> str:
        text = self.locale().toString(float(value), "f", self.decimals())
        return _trim_localized_decimal(text, self.locale().decimalPoint())


class ForestManagerMainWindow(QMainWindow if QApplication is not None else object):
    def __init__(
        self,
        controller: ForestManagerUIController | None = None,
        *,
        site_model_service: SiteModelService | None = None,
        site_model_persistence_path: str | Path | None = None,
    ) -> None:
        if QApplication is None:
            raise RuntimeError("PySide6 is required to launch the Forest Manager UI.")
        super().__init__()
        self.controller = controller or ForestManagerUIController()
        self.site_model_service = site_model_service or SiteModelService()
        self.site_viewer_presenter = SiteViewerPresenter(
            self.site_model_service, persistence_path=site_model_persistence_path
        )
        self._updating_forest_list = False
        self._updating_editors = False
        self._tables: dict[str, QTableWidget] = {}
        self._artist_editors: dict[str, QWidget] = {}
        self._updating_artist_controls = False
        self._updating_group_controls = False
        self._rendered_properties_ref = None
        self._rendered_pending_names: frozenset[str] = frozenset()
        # Plant Group controls use the already-verified controller live-write
        # endpoints. Debouncing prevents command floods while preserving the
        # final value and keeps Advanced property editing on the existing
        # pending/apply contract.
        self._live_sync_delay_ms = 75
        self._plant_group_live_timers: dict[str, QTimer] = {}
        self._plant_group_live_values: dict[str, Any] = {}
        self.setWindowTitle("Forest Manager")
        self.resize(1280, 800)
        self._build_ui()
        self.refresh_scene()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.status_label = QLabel("Not connected")
        self.units_label = QLabel("")
        self.refresh_button = QPushButton("Refresh Scene")
        self.use_selection_button = QPushButton("Use 3ds Max Selection")
        self.refresh_button.clicked.connect(self.refresh_scene)
        self.use_selection_button.clicked.connect(self.use_max_selection)
        top.addWidget(self.status_label, 1)
        top.addWidget(self.units_label)
        top.addWidget(self.use_selection_button)
        top.addWidget(self.refresh_button)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.plant_group_label = QLabel("Plant Groups (0)")
        left_layout.addWidget(self.plant_group_label)
        self.forest_list = QTreeWidget()
        self.forest_list.setHeaderHidden(True)
        self.forest_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.forest_list.currentItemChanged.connect(self._plant_group_changed)
        left_layout.addWidget(self.forest_list, 1)
        group_note = QLabel(
            "Each Plant Group maps to one or more Geometry species inside the primary Forest. "
            "Selecting a group edits only those species; no additional Forest or Area is created."
        )
        group_note.setWordWrap(True)
        left_layout.addWidget(group_note)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.selected_label = QLabel("No Forest selected")
        right_layout.addWidget(self.selected_label)

        self.group_controls = QGroupBox("Selected Plant Group")
        group_form = QFormLayout(self.group_controls)
        self.group_species_label = QLabel("-")
        self.group_species_label.setWordWrap(True)
        self.group_enabled = QCheckBox("Enabled")
        self.group_enabled.toggled.connect(self._group_enabled_changed)
        self.group_scale = CompactDoubleSpinBox()
        self.group_scale.setDecimals(2)
        self.group_scale.setRange(0.01, 10000.0)
        self.group_scale.setSuffix(" %")
        self.group_scale.valueChanged.connect(lambda value: self._schedule_plant_group_live("scale", value))
        self.group_probability = CompactDoubleSpinBox()
        self.group_probability.setDecimals(2)
        self.group_probability.setRange(0.0, 100.0)
        self.group_probability.setSuffix(" %")
        self.group_probability.valueChanged.connect(lambda value: self._schedule_plant_group_live("probability", value))
        group_form.addRow("Species", self.group_species_label)
        group_form.addRow("Visibility", self.group_enabled)
        group_form.addRow("Species Size", self.group_scale)
        group_form.addRow("Probability", self.group_probability)
        right_layout.addWidget(self.group_controls)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.addTab(self._create_artist_controls_page(), "Artist Controls")
        self.project_viewer = ProjectViewerWidget(self.site_viewer_presenter)
        self.mode_tabs.addTab(self.project_viewer, "Project Viewer")

        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_note = QLabel("Advanced Forest Pack properties. Normal production work should use Artist Controls.")
        advanced_note.setWordWrap(True)
        advanced_layout.addWidget(advanced_note)
        self.tabs = QTabWidget()
        for label in DOMAIN_TABS:
            table = self._create_property_table()
            self._tables[label] = table
            self.tabs.addTab(table, label)
        advanced_layout.addWidget(self.tabs, 1)
        self.mode_tabs.addTab(advanced, "Advanced")
        right_layout.addWidget(self.mode_tabs, 1)

        actions = QHBoxLayout()
        self.pending_label = QLabel("No pending changes")
        self.reset_button = QPushButton("Reset")
        self.revert_button = QPushButton("Revert")
        self.apply_button = QPushButton("Apply")
        self.reset_button.setToolTip("Restore the selected Plant Group, or all Forest 01 groups, to Forest Manager defaults in both the UI and 3ds Max.")
        self.reset_button.clicked.connect(self.reset_selected_target)
        self.revert_button.clicked.connect(self.revert_pending)
        self.apply_button.clicked.connect(self.apply_pending)
        actions.addWidget(self.pending_label, 1)
        actions.addWidget(self.reset_button)
        actions.addWidget(self.revert_button)
        actions.addWidget(self.apply_button)
        right_layout.addLayout(actions)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1020])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)


    def refresh_project_viewer(self) -> None:
        self.project_viewer.refresh()

    def _create_artist_controls_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Set planting intent here. Forest Manager coordinates dependent Forest Pack parameters internally; "
            "use Advanced only for exceptional technical adjustments."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        group = QGroupBox("Planting Intent")
        form = QFormLayout(group)
        for spec in artist_control_specs():
            if spec.kind == "distance":
                editor = CompactDoubleSpinBox()
                editor.setDecimals(3)
                editor.setRange(0.001, 1000000.0)
                editor.setSuffix("")
                editor.editingFinished.connect(lambda key=spec.key, w=editor: self._artist_control_changed(key, w.value()))
            else:
                editor = QComboBox()
                editor.addItems(list(spec.options))
                editor.currentTextChanged.connect(lambda value, key=spec.key: self._artist_control_changed(key, value))
            editor.setToolTip(spec.description)
            self._artist_editors[spec.key] = editor
            form.addRow(spec.label, editor)
        layout.addWidget(group)

        layout.addStretch(1)
        return page

    def _artist_control_changed(self, key: str, value: Any) -> None:
        if self._updating_artist_controls:
            return
        self._apply_state(self.controller.set_artist_control(key, value))

    def _schedule_plant_group_live(self, field: str, value: Any) -> None:
        if self._updating_group_controls:
            return
        self._plant_group_live_values[field] = value
        timer = self._plant_group_live_timers.get(field)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda live_field=field: self._flush_plant_group_live(live_field))
            self._plant_group_live_timers[field] = timer
        timer.start(self._live_sync_delay_ms)

    def _flush_plant_group_live(self, field: str) -> None:
        if field not in self._plant_group_live_values:
            return
        value = self._plant_group_live_values.pop(field)
        if field == "scale":
            self._apply_state(self.controller.set_selected_group_scale(value))
            return
        if field == "probability":
            self._apply_state(self.controller.set_selected_group_probability(value))
            return

    def _group_enabled_changed(self, enabled: bool) -> None:
        if self._updating_group_controls:
            return
        self._apply_state(self.controller.set_selected_group_enabled(bool(enabled)))

    def _group_scale_changed(self) -> None:
        if self._updating_group_controls:
            return
        self._apply_state(self.controller.set_selected_group_scale(self.group_scale.value()))

    def _group_probability_changed(self) -> None:
        if self._updating_group_controls:
            return
        self._apply_state(self.controller.set_selected_group_probability(self.group_probability.value()))

    def _create_property_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Property", "Class", "Mode", "Control", "Value"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _confirm_target_switch(self) -> bool:
        if not self.controller.state.pending_edits:
            return True
        choice = QMessageBox.question(
            self,
            "Pending changes",
            "Discard pending changes and switch planting target?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            self._apply_state(self.controller.state)
            return False
        return True

    def _plant_group_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        if self._updating_forest_list or current is None:
            return
        target_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not target_id or not self._confirm_target_switch():
            return
        if target_id == "__forest_01__":
            self._apply_state(self.controller.select_global_planting())
            return
        self._apply_state(self.controller.select_plant_group(str(target_id)))

    def _select_global_planting(self) -> None:
        if not self._confirm_target_switch():
            return
        self._apply_state(self.controller.select_global_planting())

    def _forest_changed(self, name: str) -> None:
        """Compatibility hook for older UI acceptance tests."""
        if self._updating_forest_list or not name or not self._confirm_target_switch():
            return
        self._apply_state(self.controller.select_forest(name))

    def refresh_scene(self) -> None:
        if self.controller.state.pending_edits:
            choice = QMessageBox.question(
                self,
                "Pending changes",
                "Discard pending changes and refresh the scene?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        self._apply_state(self.controller.refresh_scene(prefer_max_selection=True))

    def use_max_selection(self) -> None:
        if self.controller.state.pending_edits:
            choice = QMessageBox.question(
                self,
                "Pending changes",
                "Discard pending changes and use the current 3ds Max selection?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        self._apply_state(self.controller.select_max_selection())

    def reset_selected_target(self) -> None:
        state = self.controller.reset_selected_target()
        self._apply_state(state)
        if state.error:
            QMessageBox.warning(self, "Forest Manager", state.error)

    def revert_pending(self) -> None:
        self._apply_state(self.controller.revert_pending())

    def apply_pending(self) -> None:
        state = self.controller.apply_pending()
        self._apply_state(state)
        if state.error:
            QMessageBox.warning(self, "Forest Manager", state.error)

    def _apply_state(self, state: ForestUIState) -> None:
        self.status_label.setText(state.status)
        self.status_label.setToolTip(state.error or "")
        units = state.scene_units or {}
        display = str(units.get("display_unit") or "")
        system = str(units.get("system_type") or "")
        self.units_label.setText(f"Display: {display} | System: {system}" if display or system else "")
        if state.selected_group_label:
            self.selected_label.setText(f"Plant Group: {state.selected_group_label}")
        elif state.selected_forest:
            self.selected_label.setText("Forest 01")
        else:
            self.selected_label.setText("No planting target selected")

        runtime = state.selected_group_runtime or {}
        group_runtime_available = bool(state.selected_group_id and runtime)
        self.group_controls.setEnabled(group_runtime_available and state.bridge_online)
        self._updating_group_controls = True
        try:
            sources = runtime.get("source_names") or []
            self.group_species_label.setText(", ".join(str(value) for value in sources) if sources else "-")
            self.group_enabled.setChecked(bool(runtime.get("enabled")) if group_runtime_available else False)
            if runtime.get("scale_percent") is not None:
                self.group_scale.setValue(float(runtime.get("scale_percent")))
            if runtime.get("probability_percent") is not None:
                self.group_probability.setValue(float(runtime.get("probability_percent")))
        finally:
            self._updating_group_controls = False

        current_group_ids: tuple[str, ...] = ()
        root_item = self.forest_list.topLevelItem(0)
        if root_item is not None:
            current_group_ids = tuple(
                str(root_item.child(i).data(0, Qt.ItemDataRole.UserRole) or "")
                for i in range(root_item.childCount())
            )
        next_group_ids = tuple(group.group_id for group in state.plant_groups)
        if current_group_ids != next_group_ids:
            self._updating_forest_list = True
            try:
                self.forest_list.clear()
                root_item = QTreeWidgetItem(["Forest 01"])
                root_item.setData(0, Qt.ItemDataRole.UserRole, "__forest_01__")
                root_item.setToolTip(0, "Scene Forest group. Expand to edit its Plant Groups.")
                self.forest_list.addTopLevelItem(root_item)
                for group in state.plant_groups:
                    item = QTreeWidgetItem([group.label])
                    item.setData(0, Qt.ItemDataRole.UserRole, group.group_id)
                    item.setToolTip(0, "Artist planting group")
                    root_item.addChild(item)
                root_item.setExpanded(True)
            finally:
                self._updating_forest_list = False
        self.plant_group_label.setText(f"Plant Groups ({len(state.plant_groups)})")
        self.forest_list.setEnabled(bool(state.primary_forest) and state.bridge_online)

        self._updating_forest_list = True
        try:
            root_item = self.forest_list.topLevelItem(0)
            if state.selected_group_id and root_item is not None:
                for index in range(root_item.childCount()):
                    item = root_item.child(index)
                    if item.data(0, Qt.ItemDataRole.UserRole) == state.selected_group_id:
                        self.forest_list.setCurrentItem(item)
                        break
            elif state.selected_forest and root_item is not None:
                self.forest_list.setCurrentItem(root_item)
            else:
                self.forest_list.clearSelection()
                self.forest_list.setCurrentItem(None)
        finally:
            self._updating_forest_list = False

        self._updating_artist_controls = True
        try:
            for control in state.artist_controls:
                editor = self._artist_editors.get(control.key)
                if editor is None:
                    continue
                editor.setEnabled(bool(control.available))
                editor.setToolTip(control.description)
                if isinstance(editor, QDoubleSpinBox):
                    editor.setSuffix(f" {control.display_suffix}" if control.display_suffix else "")
                    if control.value is not None:
                        editor.setValue(float(control.value))
                elif isinstance(editor, QComboBox):
                    index = editor.findText(str(control.value))
                    if index >= 0:
                        editor.setCurrentIndex(index)
        finally:
            self._updating_artist_controls = False

        pending_names = {edit.property_name for edit in state.pending_edits}
        self.pending_label.setText(
            f"{len(state.pending_edits)} pending change(s)" if state.pending_edits else "No pending changes"
        )
        self.apply_button.setEnabled(bool(state.pending_edits) and state.bridge_online)
        self.revert_button.setEnabled(bool(state.pending_edits))
        self.reset_button.setEnabled(bool(state.selected_forest) and state.bridge_online)

        property_pending_names = frozenset(
            name for name in pending_names if not name.startswith("__plant_group__|")
        )
        if (
            self._rendered_properties_ref is not state.properties
            or self._rendered_pending_names != property_pending_names
        ):
            for label, table in self._tables.items():
                rows = state.properties if label == "All Properties" else tuple(
                    row for row in state.properties if row.domain == label
                )
                self._populate_properties(table, rows, pending_names)
            self._rendered_properties_ref = state.properties
            self._rendered_pending_names = property_pending_names

        self.statusBar().showMessage(state.error or state.status)

    def _populate_properties(self, table: QTableWidget, properties: tuple[PropertyRow, ...], pending_names: set[str]) -> None:
        self._updating_editors = True
        try:
            table.setRowCount(len(properties))
            for row_index, prop in enumerate(properties):
                metadata = (prop.name, prop.value_class, prop.write_mode, prop.control)
                for column, value in enumerate(metadata):
                    item = QTableWidgetItem(str(value))
                    if prop.write_mode == "read_only":
                        item.setToolTip("Read-only Forest Pack control")
                    table.setItem(row_index, column, item)
                self._install_editor(table, row_index, prop, prop.name in pending_names)
            table.resizeColumnsToContents()
        finally:
            self._updating_editors = False

    def _install_editor(self, table: QTableWidget, row_index: int, prop: PropertyRow, dirty: bool) -> None:
        if not prop.writable:
            text = _format_value(prop.value)
            if prop.array_metadata:
                count = prop.array_metadata.get("count")
                if count is not None:
                    text = f"{text}  [count={count}]"
            item = QTableWidgetItem(text)
            item.setToolTip("Read-only or specialized adapter; editing will be exposed by a dedicated UI control.")
            table.setItem(row_index, 4, item)
            return

        value = next((edit.value for edit in self.controller.state.pending_edits if edit.property_name == prop.name), prop.value)
        editor: QWidget
        if prop.editor_kind == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.stateChanged.connect(lambda _state, name=prop.name, w=widget: self._editor_changed(name, w.isChecked()))
            editor = widget
        elif prop.editor_kind == "int":
            widget = QSpinBox()
            widget.setRange(-2147483648, 2147483647)
            widget.setValue(int(value or 0))
            widget.valueChanged.connect(lambda current, name=prop.name: self._editor_changed(name, current))
            editor = widget
        elif prop.editor_kind == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(6)
            widget.setRange(-1.0e12, 1.0e12)
            widget.setValue(float(value or 0.0))
            widget.valueChanged.connect(lambda current, name=prop.name: self._editor_changed(name, current))
            editor = widget
        else:
            widget = QLineEdit(_format_value(value))
            if prop.editor_kind == "color":
                widget.setPlaceholderText("R, G, B")
            widget.editingFinished.connect(lambda name=prop.name, w=widget: self._editor_changed(name, w.text()))
            editor = widget
        if dirty:
            editor.setToolTip("Pending change")
        table.setCellWidget(row_index, 4, editor)

    def _editor_changed(self, property_name: str, value: Any) -> None:
        if self._updating_editors:
            return
        state = self.controller.set_pending_value(property_name, value)
        self._apply_state(state)


def run() -> int:
    if QApplication is None:
        raise RuntimeError("PySide6 is required to launch the Forest Manager UI.")
    app = QApplication.instance() or QApplication([])
    window = ForestManagerMainWindow()
    window.show()
    return int(app.exec())
