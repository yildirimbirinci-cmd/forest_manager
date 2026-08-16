from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .schema import AnnotationSource, SemanticAnnotation, SemanticRole
from .service import SiteModelError, SiteModelService


@dataclass(frozen=True)
class ViewerSelectionState:
    geometry_ids: tuple[str, ...] = ()
    active_geometry_id: str | None = None


@dataclass(frozen=True)
class ViewerCorrectionResult:
    geometry_ids: tuple[str, ...]
    annotations: tuple[SemanticAnnotation, ...]


class SiteModelViewerInteraction:
    """Selection and artist-supervision workflow for the project viewer.

    The viewer never edits imported geometry implicitly. It records artist
    confirmation, correction, or rejection as higher-priority annotations.
    """

    def __init__(
        self,
        service: SiteModelService,
        *,
        persistence_path: str | Path | None = None,
    ) -> None:
        self.service = service
        self.persistence_path = None if persistence_path is None else Path(persistence_path)
        self._selection = ViewerSelectionState()

    @property
    def selection(self) -> ViewerSelectionState:
        return self._selection

    def select(self, geometry_ids: Iterable[str], *, active_geometry_id: str | None = None) -> ViewerSelectionState:
        ordered: list[str] = []
        seen: set[str] = set()
        for geometry_id in geometry_ids:
            value = str(geometry_id).strip()
            if not value or value in seen:
                continue
            self.service.geometry(value)
            ordered.append(value)
            seen.add(value)
        active = None if active_geometry_id is None else str(active_geometry_id).strip()
        if active and active not in seen:
            raise SiteModelError("active viewer geometry must be part of the current selection")
        if not active and ordered:
            active = ordered[0]
        self._selection = ViewerSelectionState(tuple(ordered), active)
        return self._selection

    def clear_selection(self) -> ViewerSelectionState:
        self._selection = ViewerSelectionState()
        return self._selection

    def approve_selected(self, *, notes: str = "") -> ViewerCorrectionResult:
        self._require_selection()
        annotations: list[SemanticAnnotation] = []
        for geometry_id in self._selection.geometry_ids:
            resolved = self.service.resolved_annotation(geometry_id)
            if resolved is None or resolved.role is SemanticRole.UNKNOWN:
                raise SiteModelError(f"cannot approve geometry without an AI semantic role: {geometry_id}")
            annotations.append(
                self.service.apply_artist_confirmation(
                    geometry_id,
                    resolved.role,
                    label=resolved.label,
                    notes=str(notes),
                )
            )
        self._persist()
        return ViewerCorrectionResult(self._selection.geometry_ids, tuple(annotations))

    def assign_role(
        self,
        role: SemanticRole | str,
        *,
        label: str = "",
        notes: str = "",
    ) -> ViewerCorrectionResult:
        self._require_selection()
        semantic_role = role if isinstance(role, SemanticRole) else SemanticRole(str(role))
        annotations: list[SemanticAnnotation] = []
        for geometry_id in self._selection.geometry_ids:
            current = self.service.resolved_annotation(geometry_id)
            if current is not None and current.source is AnnotationSource.AI_INFERRED and current.role is semantic_role:
                annotation = self.service.apply_artist_confirmation(
                    geometry_id,
                    semantic_role,
                    label=label or current.label,
                    notes=notes,
                )
            else:
                annotation = self.service.apply_artist_override(
                    geometry_id,
                    semantic_role,
                    label=label,
                    notes=notes,
                )
            annotations.append(annotation)
        self._persist()
        return ViewerCorrectionResult(self._selection.geometry_ids, tuple(annotations))

    def reject_selected(self, *, notes: str = "") -> ViewerCorrectionResult:
        return self.assign_role(
            SemanticRole.UNKNOWN,
            notes=notes or "Artist rejected AI semantic classification",
        )

    def _require_selection(self) -> None:
        if not self._selection.geometry_ids:
            raise SiteModelError("viewer correction requires at least one selected geometry")

    def _persist(self) -> None:
        if self.persistence_path is not None:
            self.service.save(self.persistence_path)
