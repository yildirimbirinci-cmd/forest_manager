from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .schema import AnnotationSource, SemanticRole
from .service import SiteModelService
from .semantic_classification import SemanticAnalysisResult, SemanticClassificationPipeline
from .viewer_binding import SiteModelViewerBinding, ViewerBindingSnapshot
from .viewer_interaction import SiteModelViewerInteraction


@dataclass(frozen=True)
class ProjectViewerState:
    revision: int
    geometry_count: int
    selected_geometry_ids: tuple[str, ...]
    active_geometry_id: str | None
    active_role: SemanticRole | None
    active_source: AnnotationSource | None
    active_confidence: float | None
    active_label: str
    status: str
    error: str | None = None
    active_source_id: str | None = None
    source_ids: tuple[str, ...] = ()
    available_layers: tuple[str, ...] = ()
    available_pages: tuple[int, ...] = ()
    visible_annotation_sources: tuple[AnnotationSource, ...] = tuple(AnnotationSource)
    low_confidence_review_enabled: bool = False
    confidence_threshold: float = 0.5
    review_geometry_count: int = 0
    selection_roles: tuple[SemanticRole, ...] = ()
    selection_sources: tuple[AnnotationSource, ...] = ()
    selection_mixed_roles: bool = False
    selection_mixed_sources: bool = False


class SiteViewerPresenter:
    """Qt-independent orchestration for project-viewer filtering and batch correction."""

    def __init__(
        self,
        service: SiteModelService,
        *,
        persistence_path: str | Path | None = None,
        interaction: SiteModelViewerInteraction | None = None,
        binding: SiteModelViewerBinding | None = None,
        semantic_pipeline: SemanticClassificationPipeline | None = None,
    ) -> None:
        self.service = service
        self.interaction = interaction or SiteModelViewerInteraction(service, persistence_path=persistence_path)
        self.binding = binding or SiteModelViewerBinding()
        self.semantic_pipeline = semantic_pipeline or SemanticClassificationPipeline()
        self._active_source_id: str | None = None
        self._visible_annotation_sources: tuple[AnnotationSource, ...] = tuple(AnnotationSource)
        self._low_confidence_review_enabled = False
        self._confidence_threshold = 0.5

    @property
    def active_source_id(self) -> str | None:
        return self._active_source_id

    @property
    def visible_annotation_sources(self) -> tuple[AnnotationSource, ...]:
        return self._visible_annotation_sources

    def snapshot(self) -> ViewerBindingSnapshot:
        return self.binding.build(
            self.service,
            interaction=self.interaction,
            source_id=self._active_source_id,
            annotation_sources=self._visible_annotation_sources,
            max_confidence=self._confidence_threshold if self._low_confidence_review_enabled else None,
            confidence_source=AnnotationSource.AI_INFERRED if self._low_confidence_review_enabled else None,
        )

    def all_sources_snapshot(self) -> ViewerBindingSnapshot:
        return self.binding.build(self.service, interaction=self.interaction)

    def state(self, *, status: str = "Project viewer ready", error: str | None = None) -> ProjectViewerState:
        snapshot = self.snapshot()
        selection = self.interaction.selection
        records_by_id = {record.geometry_id: record for record in snapshot.records}
        active_record = records_by_id.get(selection.active_geometry_id) if selection.active_geometry_id else None
        selected_records = [records_by_id[item] for item in selection.geometry_ids if item in records_by_id]
        roles = tuple(sorted({r.role for r in selected_records if r.role is not None}, key=lambda r: r.value))
        sources = tuple(sorted({r.annotation_source for r in selected_records if r.annotation_source is not None}, key=lambda s: s.value))
        return ProjectViewerState(
            revision=snapshot.revision,
            geometry_count=len(snapshot.records),
            selected_geometry_ids=selection.geometry_ids,
            active_geometry_id=selection.active_geometry_id,
            active_role=None if active_record is None else active_record.role,
            active_source=None if active_record is None else active_record.annotation_source,
            active_confidence=None if active_record is None else active_record.confidence,
            active_label="" if active_record is None else active_record.label,
            status=status,
            error=error,
            active_source_id=self._active_source_id,
            source_ids=snapshot.source_ids,
            available_layers=snapshot.layers,
            available_pages=snapshot.page_indexes,
            visible_annotation_sources=self._visible_annotation_sources,
            low_confidence_review_enabled=self._low_confidence_review_enabled,
            confidence_threshold=self._confidence_threshold,
            review_geometry_count=len(snapshot.records) if self._low_confidence_review_enabled else 0,
            selection_roles=roles,
            selection_sources=sources,
            selection_mixed_roles=len(roles) > 1,
            selection_mixed_sources=len(sources) > 1,
        )

    def set_active_source(self, source_id: str | None) -> ProjectViewerState:
        requested = None if source_id in (None, "", "__all__") else str(source_id)
        sources = self.all_sources_snapshot().source_ids
        if requested is not None and requested not in sources:
            raise ValueError(f"unknown project source: {requested}")
        self._active_source_id = requested
        self._prune_selection_to_visible()
        label = "all sources" if requested is None else requested
        return self.state(status=f"Showing {label}")

    def set_annotation_source_visible(self, source: AnnotationSource | str, visible: bool) -> ProjectViewerState:
        value = source if isinstance(source, AnnotationSource) else AnnotationSource(str(source))
        current = list(self._visible_annotation_sources)
        if visible and value not in current:
            current.append(value)
        if not visible and value in current:
            current.remove(value)
        self._visible_annotation_sources = tuple(item for item in AnnotationSource if item in current)
        self._prune_selection_to_visible()
        return self.state(status="Semantic overlay filters updated")

    def set_low_confidence_review(self, enabled: bool, *, threshold: float | None = None) -> ProjectViewerState:
        if threshold is not None:
            value = float(threshold)
            if not 0.0 <= value <= 1.0:
                raise ValueError("confidence threshold must be between 0 and 1")
            self._confidence_threshold = value
        self._low_confidence_review_enabled = bool(enabled)
        self._prune_selection_to_visible()
        if self._low_confidence_review_enabled:
            return self.state(status=f"Reviewing AI confidence <= {self._confidence_threshold:.2f}")
        return self.state(status="Low-confidence review disabled")

    def reanalyze_semantics(self) -> tuple[ProjectViewerState, SemanticAnalysisResult]:
        visible_ids = tuple(record.geometry_id for record in self.snapshot().records)
        result = self.semantic_pipeline.analyze(self.service, visible_ids)
        return self.state(status=f"AI semantic analysis updated {len(result.classified_geometry_ids)} geometry item(s)"), result

    def select(self, geometry_id: str, *, additive: bool = False, toggle: bool = False) -> ProjectViewerState:
        geometry_id = str(geometry_id)
        visible = {record.geometry_id for record in self.snapshot().records}
        if geometry_id not in visible:
            raise ValueError(f"geometry is not visible in the current viewer filter: {geometry_id}")
        current = list(self.interaction.selection.geometry_ids) if additive else []
        if toggle and geometry_id in current:
            current.remove(geometry_id)
            active = current[-1] if current else None
            self.interaction.select(current, active_geometry_id=active)
            return self.state(status=f"Deselected {geometry_id}")
        if geometry_id not in current:
            current.append(geometry_id)
        self.interaction.select(current, active_geometry_id=geometry_id)
        return self.state(status=f"Selected {geometry_id}")

    def select_all_visible(self) -> ProjectViewerState:
        ids = tuple(record.geometry_id for record in self.snapshot().records)
        self.interaction.select(ids, active_geometry_id=ids[0] if ids else None)
        return self.state(status=f"Selected {len(ids)} visible geometry item(s)")

    def clear_selection(self) -> ProjectViewerState:
        self.interaction.clear_selection()
        return self.state(status="Selection cleared")

    def approve(self, *, notes: str = "") -> ProjectViewerState:
        result = self.interaction.approve_selected(notes=notes)
        return self.state(status=f"Approved {len(result.geometry_ids)} geometry item(s)")

    def assign_role(self, role: SemanticRole | str, *, notes: str = "") -> ProjectViewerState:
        semantic_role = role if isinstance(role, SemanticRole) else SemanticRole(str(role))
        result = self.interaction.assign_role(semantic_role, notes=notes)
        return self.state(status=f"Assigned {semantic_role.value} to {len(result.geometry_ids)} geometry item(s)")

    def reject(self, *, notes: str = "") -> ProjectViewerState:
        result = self.interaction.reject_selected(notes=notes)
        return self.state(status=f"Rejected {len(result.geometry_ids)} geometry item(s)")

    def _prune_selection_to_visible(self) -> None:
        selection = self.interaction.selection
        if not selection.geometry_ids:
            return
        visible_ids = {record.geometry_id for record in self.snapshot().records}
        kept = tuple(item for item in selection.geometry_ids if item in visible_ids)
        if kept:
            active = selection.active_geometry_id if selection.active_geometry_id in kept else kept[0]
            self.interaction.select(kept, active_geometry_id=active)
        else:
            self.interaction.clear_selection()
