from __future__ import annotations

from typing import Any

from .controller import ForestManagerUIController, ForestUIState, PropertyRow

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPushButton,
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


class ForestManagerMainWindow(QMainWindow if QApplication is not None else object):
    def __init__(self, controller: ForestManagerUIController | None = None) -> None:
        if QApplication is None:
            raise RuntimeError("PySide6 is required to launch the Forest Manager UI.")
        super().__init__()
        self.controller = controller or ForestManagerUIController()
        self._updating_forest_list = False
        self.setWindowTitle("Forest Manager")
        self.resize(1180, 760)
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
        self.tabs = QTabWidget()
        self.property_table = self._create_property_table()
        self.tabs.addTab(self.property_table, DOMAIN_TABS[0])
        for label in DOMAIN_TABS[1:]:
            placeholder = QLabel(f"{label} panel will be connected to the semantic controls in the next Stage 7 block.")
            placeholder.setWordWrap(True)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.addWidget(placeholder)
            layout.addStretch(1)
            self.tabs.addTab(container, label)
        right_layout.addWidget(self.tabs, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 920])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _create_property_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Property", "Class", "Mode", "Value"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _forest_changed(self, name: str) -> None:
        if self._updating_forest_list or not name:
            return
        self._apply_state(self.controller.select_forest(name))

    def refresh_scene(self) -> None:
        self._apply_state(self.controller.refresh_scene(prefer_max_selection=True))

    def use_max_selection(self) -> None:
        self._apply_state(self.controller.select_max_selection())

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
        self._populate_properties(state.properties)

        if state.error:
            self.statusBar().showMessage(state.error)
        else:
            self.statusBar().showMessage(state.status)

    def _populate_properties(self, properties: tuple[PropertyRow, ...]) -> None:
        self.property_table.setRowCount(len(properties))
        for row, prop in enumerate(properties):
            values = (prop.name, prop.value_class, prop.write_mode, _format_value(prop.value))
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 2 and prop.write_mode == "read_only":
                    item.setToolTip("Read-only Forest Pack control")
                self.property_table.setItem(row, column, item)
        self.property_table.resizeColumnsToContents()


def run() -> int:
    if QApplication is None:
        raise RuntimeError("PySide6 is required to launch the Forest Manager UI.")
    app = QApplication.instance() or QApplication([])
    window = ForestManagerMainWindow()
    window.show()
    return int(app.exec())
