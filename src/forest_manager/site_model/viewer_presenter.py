from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .schema import AnnotationSource, SemanticRole
from .service import SiteModelService
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


class SiteViewerPresenter:
    """Qt-independent orchestration for project-viewer selection and correction."""

    def __init__(
        self,
        service: SiteModelService,
        *,
        persistence_path: str | Path | None = None,
        interaction: SiteModelViewerInteraction | None = None,
        binding: SiteModelViewerBinding | None = None,
    ) -> None:
        self.service = service
        self.interaction = interaction or SiteModelViewerInteraction(service, persistence_path=persistence_path)
        self.binding = binding or SiteModelViewerBinding()

    def snapshot(self) -> ViewerBindingSnapshot:
        return self.binding.build(self.service, interaction=self.interaction)

    def state(self, *, status: str = "Project viewer ready", error: str | None = None) -> ProjectViewerState:
        snapshot = self.snapshot()
        selection = self.interaction.selection
        active_record = None
        if selection.active_geometry_id is not None:
            active_record = next(
                (record for record in snapshot.records if record.geometry_id == selection.active_geometry_id),
                None,
            )
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
        )

    def select(self, geometry_id: str, *, additive: bool = False) -> ProjectViewerState:
        geometry_id = str(geometry_id)
        current = list(self.interaction.selection.geometry_ids) if additive else []
        if geometry_id not in current:
            current.append(geometry_id)
        self.interaction.select(current, active_geometry_id=geometry_id)
        return self.state(status=f"Selected {geometry_id}")

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
