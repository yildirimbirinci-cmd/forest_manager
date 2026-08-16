from __future__ import annotations

from typing import Any

from forest_manager.site_model import (
    AnnotationSource,
    GeometryKind,
    ProjectViewerState,
    SemanticRole,
    SiteViewerPresenter,
    ViewerRenderRecord,
)

try:
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QGraphicsPathItem,
        QGraphicsScene,
        QGraphicsSimpleTextItem,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = None


if QWidget is not None:
    class _GeometryPathItem(QGraphicsPathItem):
        def __init__(self, owner: "ProjectViewerWidget", record: ViewerRenderRecord, path: QPainterPath) -> None:
            super().__init__(path)
            self.owner = owner
            self.record = record
            self.setToolTip(owner._record_tooltip(record))
            self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)

        def mousePressEvent(self, event: Any) -> None:
            additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.owner.select_geometry(self.record.geometry_id, additive=additive)
            event.accept()


    class ProjectViewerWidget(QWidget):
        """Interactive CAD/PDF viewer using semantic state from the Site Model."""

        def __init__(self, presenter: SiteViewerPresenter, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.presenter = presenter
            self._items: dict[str, _GeometryPathItem] = {}
            self._labels: list[QGraphicsSimpleTextItem] = []
            self._updating_filters = False
            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)

            filters = QHBoxLayout()
            filters.addWidget(QLabel("Source"))
            self.source_combo = QComboBox()
            self.source_combo.currentIndexChanged.connect(self._source_changed)
            filters.addWidget(self.source_combo, 1)
            self.ai_overlay = QCheckBox("AI")
            self.confirmed_overlay = QCheckBox("Artist Confirmed")
            self.override_overlay = QCheckBox("Artist Override")
            self.labels_overlay = QCheckBox("Role Labels")
            for checkbox in (self.ai_overlay, self.confirmed_overlay, self.override_overlay, self.labels_overlay):
                checkbox.setChecked(True)
            self.ai_overlay.toggled.connect(
                lambda checked: self._overlay_changed(AnnotationSource.AI_INFERRED, checked)
            )
            self.confirmed_overlay.toggled.connect(
                lambda checked: self._overlay_changed(AnnotationSource.ARTIST_CONFIRMED, checked)
            )
            self.override_overlay.toggled.connect(
                lambda checked: self._overlay_changed(AnnotationSource.ARTIST_OVERRIDE, checked)
            )
            self.labels_overlay.toggled.connect(lambda _checked: self.refresh())
            filters.addWidget(self.ai_overlay)
            filters.addWidget(self.confirmed_overlay)
            filters.addWidget(self.override_overlay)
            filters.addWidget(self.labels_overlay)
            root.addLayout(filters)

            self.info_label = QLabel("No project geometry loaded")
            self.info_label.setWordWrap(True)
            root.addWidget(self.info_label)

            self.scene = QGraphicsScene(self)
            self.view = QGraphicsView(self.scene)
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            root.addWidget(self.view, 1)

            controls = QHBoxLayout()
            self.role_combo = QComboBox()
            for role in SemanticRole:
                self.role_combo.addItem(role.value.replace("_", " ").title(), role.value)
            self.approve_button = QPushButton("Approve AI Role")
            self.assign_button = QPushButton("Assign Role")
            self.reject_button = QPushButton("Reject")
            self.clear_button = QPushButton("Clear Selection")
            self.approve_button.clicked.connect(self.approve_selected)
            self.assign_button.clicked.connect(self.assign_selected_role)
            self.reject_button.clicked.connect(self.reject_selected)
            self.clear_button.clicked.connect(self.clear_selection)
            controls.addWidget(self.role_combo, 1)
            controls.addWidget(self.approve_button)
            controls.addWidget(self.assign_button)
            controls.addWidget(self.reject_button)
            controls.addWidget(self.clear_button)
            root.addLayout(controls)

            self.status_label = QLabel("Project viewer ready")
            root.addWidget(self.status_label)

        def refresh(self) -> None:
            snapshot = self.presenter.snapshot()
            self.scene.clear()
            self._items.clear()
            self._labels.clear()
            for record in snapshot.records:
                item = _GeometryPathItem(self, record, self._record_path(record))
                item.setPen(self._record_pen(record))
                item.setZValue(20.0 if record.active else (10.0 if record.selected else 0.0))
                self.scene.addItem(item)
                self._items[record.geometry_id] = item
                if self.labels_overlay.isChecked() and record.role is not None:
                    label = QGraphicsSimpleTextItem(record.role.value.replace("_", " "))
                    label.setToolTip(self._record_tooltip(record))
                    label.setPos(record.bounds.min_x, -record.bounds.max_y)
                    label.setZValue(30.0)
                    self.scene.addItem(label)
                    self._labels.append(label)

            if snapshot.bounds is not None:
                width = max(snapshot.bounds.max_x - snapshot.bounds.min_x, 1.0)
                height = max(snapshot.bounds.max_y - snapshot.bounds.min_y, 1.0)
                rect = QRectF(snapshot.bounds.min_x, -snapshot.bounds.max_y, width, height)
                self.scene.setSceneRect(rect.adjusted(-10.0, -10.0, 10.0, 10.0))
                self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._apply_state(self.presenter.state())

        @staticmethod
        def _record_path(record: ViewerRenderRecord) -> QPainterPath:
            path = QPainterPath()
            first = record.points[0]
            if record.kind is GeometryKind.POINT:
                radius = 1.5
                path.addEllipse(first.x - radius, -first.y - radius, radius * 2.0, radius * 2.0)
                return path
            path.moveTo(first.x, -first.y)
            for point in record.points[1:]:
                path.lineTo(point.x, -point.y)
            if record.closed:
                path.closeSubpath()
            return path

        @staticmethod
        def _record_pen(record: ViewerRenderRecord) -> QPen:
            pen = QPen()
            pen.setWidthF(2.8 if record.selected else 1.4)
            if record.annotation_source is AnnotationSource.AI_INFERRED:
                pen.setColor(QColor("#6aa9ff"))
                pen.setStyle(Qt.PenStyle.DashLine)
            elif record.annotation_source is AnnotationSource.ARTIST_CONFIRMED:
                pen.setColor(QColor("#5ccf7a"))
                pen.setStyle(Qt.PenStyle.SolidLine)
            elif record.annotation_source is AnnotationSource.ARTIST_OVERRIDE:
                pen.setColor(QColor("#ffad4d"))
                pen.setStyle(Qt.PenStyle.DotLine)
            else:
                pen.setColor(QColor("#9aa0a6"))
                pen.setStyle(Qt.PenStyle.SolidLine)
            if record.active:
                pen.setWidthF(3.4)
            return pen

        @staticmethod
        def _record_tooltip(record: ViewerRenderRecord) -> str:
            role = "unclassified" if record.role is None else record.role.value
            source = "none" if record.annotation_source is None else record.annotation_source.value
            location = record.layer or (f"page {record.page_index + 1}" if record.page_index is not None else "")
            return f"{record.geometry_id}\nRole: {role}\nSemantic source: {source}\n{location}".strip()

        def _source_changed(self, _index: int) -> None:
            if self._updating_filters:
                return
            try:
                value = self.source_combo.currentData()
                self.presenter.set_active_source(None if value in (None, "__all__") else str(value))
                self.refresh()
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Source switch failed", error=f"{type(exc).__name__}: {exc}"))

        def _overlay_changed(self, source: AnnotationSource, checked: bool) -> None:
            if self._updating_filters:
                return
            try:
                self.presenter.set_annotation_source_visible(source, checked)
                self.refresh()
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Overlay update failed", error=f"{type(exc).__name__}: {exc}"))

        def select_geometry(self, geometry_id: str, *, additive: bool = False) -> None:
            try:
                state = self.presenter.select(geometry_id, additive=additive)
                self.refresh()
                self._apply_state(state)
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Selection failed", error=f"{type(exc).__name__}: {exc}"))

        def clear_selection(self) -> None:
            state = self.presenter.clear_selection()
            self.refresh()
            self._apply_state(state)

        def approve_selected(self) -> None:
            try:
                state = self.presenter.approve()
                self.refresh()
                self._apply_state(state)
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Approval failed", error=f"{type(exc).__name__}: {exc}"))

        def assign_selected_role(self) -> None:
            try:
                state = self.presenter.assign_role(str(self.role_combo.currentData()))
                self.refresh()
                self._apply_state(state)
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Role assignment failed", error=f"{type(exc).__name__}: {exc}"))

        def reject_selected(self) -> None:
            try:
                state = self.presenter.reject()
                self.refresh()
                self._apply_state(state)
            except Exception as exc:
                self._apply_state(self.presenter.state(status="Rejection failed", error=f"{type(exc).__name__}: {exc}"))

        def _apply_state(self, state: ProjectViewerState) -> None:
            self._sync_source_combo(state)
            selected = len(state.selected_geometry_ids)
            source = "none" if state.active_source is None else state.active_source.value
            role = "none" if state.active_role is None else state.active_role.value
            confidence = "" if state.active_confidence is None else f" | confidence {state.active_confidence:.2f}"
            project_source = "all" if state.active_source_id is None else state.active_source_id
            self.info_label.setText(
                f"Geometry: {state.geometry_count} | Selected: {selected} | Role: {role} | "
                f"Source: {source}{confidence} | Project: {project_source}"
            )
            self.status_label.setText(state.error or state.status)
            self.status_label.setToolTip(state.error or "")
            has_selection = bool(state.selected_geometry_ids)
            self.approve_button.setEnabled(has_selection)
            self.assign_button.setEnabled(has_selection)
            self.reject_button.setEnabled(has_selection)
            self.clear_button.setEnabled(has_selection)

        def _sync_source_combo(self, state: ProjectViewerState) -> None:
            desired = "__all__" if state.active_source_id is None else state.active_source_id
            current_values = tuple(self.source_combo.itemData(i) for i in range(self.source_combo.count()))
            expected = ("__all__",) + state.source_ids
            if current_values == expected:
                return
            self._updating_filters = True
            try:
                self.source_combo.clear()
                self.source_combo.addItem("All Sources", "__all__")
                for source_id in state.source_ids:
                    self.source_combo.addItem(source_id, source_id)
                index = self.source_combo.findData(desired)
                self.source_combo.setCurrentIndex(max(index, 0))
            finally:
                self._updating_filters = False
else:
    class ProjectViewerWidget:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PySide6 is required to create the Forest Manager project viewer.")


__all__ = ["ProjectViewerWidget"]
