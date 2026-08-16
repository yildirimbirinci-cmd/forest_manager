from __future__ import annotations

from typing import Any

from .controller import ForestManagerUIController, ForestUIState, PropertyRow
from .semantic_controls import artist_control_specs

try:
    from PySide6.QtCore import Qt
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
        QListWidget,
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
    def __init__(self, controller: ForestManagerUIController | None = None) -> None:
        if QApplication is None:
            raise RuntimeError("PySide6 is required to launch the Forest Manager UI.")
        super().__init__()
        self.controller = controller or ForestManagerUIController()
        self._updating_forest_list = False
        self._updating_editors = False
        self._tables: dict[str, QTableWidget] = {}
        self._artist_editors: dict[str, QWidget] = {}
        self._updating_artist_controls = False
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
        self.forest_list = QListWidget()
        self.forest_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.forest_list.currentTextChanged.connect(self._forest_changed)
        splitter.addWidget(self.forest_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.selected_label = QLabel("No Forest selected")
        right_layout.addWidget(self.selected_label)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.addTab(self._create_artist_controls_page(), "Artist Controls")

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
        self.revert_button = QPushButton("Revert")
        self.apply_button = QPushButton("Apply")
        self.revert_button.clicked.connect(self.revert_pending)
        self.apply_button.clicked.connect(self.apply_pending)
        actions.addWidget(self.pending_label, 1)
        actions.addWidget(self.revert_button)
        actions.addWidget(self.apply_button)
        right_layout.addLayout(actions)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1020])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)


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

    def _create_property_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Property", "Class", "Mode", "Control", "Value"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _forest_changed(self, name: str) -> None:
        if self._updating_forest_list or not name:
            return
        if self.controller.state.pending_edits:
            choice = QMessageBox.question(
                self,
                "Pending changes",
                "Discard pending changes and switch Forest?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                self._apply_state(self.controller.state)
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
        self.selected_label.setText(state.selected_forest or "No Forest selected")

        current_names = tuple(self.forest_list.item(i).text() for i in range(self.forest_list.count()))
        if current_names != state.forest_names:
            self._updating_forest_list = True
            try:
                self.forest_list.clear()
                self.forest_list.addItems(list(state.forest_names))
            finally:
                self._updating_forest_list = False
        if state.selected_forest:
            matches = self.forest_list.findItems(state.selected_forest, Qt.MatchFlag.MatchExactly)
            if matches and self.forest_list.currentItem() is not matches[0]:
                self._updating_forest_list = True
                try:
                    self.forest_list.setCurrentItem(matches[0])
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

        for label, table in self._tables.items():
            rows = state.properties if label == "All Properties" else tuple(row for row in state.properties if row.domain == label)
            self._populate_properties(table, rows, pending_names)

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
