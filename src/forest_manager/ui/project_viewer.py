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
    from PySide6.QtGui import QPainterPath, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QGraphicsPathItem,
        QGraphicsScene,
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
            self.setToolTip(record.geometry_id)
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
            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
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
            for record in snapshot.records:
                item = _GeometryPathItem(self, record, self._record_path(record))
                pen = QPen()
                pen.setWidthF(2.4 if record.selected else 1.2)
                if record.annotation_source is AnnotationSource.AI_INFERRED:
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif record.annotation_source is AnnotationSource.ARTIST_OVERRIDE:
                    pen.setStyle(Qt.PenStyle.DotLine)
                else:
                    pen.setStyle(Qt.PenStyle.SolidLine)
                item.setPen(pen)
                item.setZValue(20.0 if record.active else (10.0 if record.selected else 0.0))
                self.scene.addItem(item)
                self._items[record.geometry_id] = item

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
            selected = len(state.selected_geometry_ids)
            source = "none" if state.active_source is None else state.active_source.value
            role = "none" if state.active_role is None else state.active_role.value
            confidence = "" if state.active_confidence is None else f" | confidence {state.active_confidence:.2f}"
            self.info_label.setText(
                f"Geometry: {state.geometry_count} | Selected: {selected} | Role: {role} | Source: {source}{confidence}"
            )
            self.status_label.setText(state.error or state.status)
            self.status_label.setToolTip(state.error or "")
            has_selection = bool(state.selected_geometry_ids)
            self.approve_button.setEnabled(has_selection)
            self.assign_button.setEnabled(has_selection)
            self.reject_button.setEnabled(has_selection)
            self.clear_button.setEnabled(has_selection)
else:
    class ProjectViewerWidget:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PySide6 is required to create the Forest Manager project viewer.")


__all__ = ["ProjectViewerWidget"]
