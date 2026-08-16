from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import AnnotationSource, GeometryKind, SemanticRole, SitePoint
from .service import SiteModelService


@dataclass(frozen=True)
class ViewerGeometryRecord:
    geometry_id: str
    kind: GeometryKind
    points: tuple[SitePoint, ...]
    closed: bool
    source_ref: str
    source_id: str
    source_kind: str
    source_path: str
    entity_id: str
    layer: str
    page_index: int | None
    role: SemanticRole | None
    annotation_source: AnnotationSource | None
    confidence: float | None
    label: str
    notes: str
    reason: str
    evidence: tuple[str, ...]
    artist_confirmed: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ViewerSnapshot:
    revision: int
    records: tuple[ViewerGeometryRecord, ...]

    def by_geometry_id(self, geometry_id: str) -> ViewerGeometryRecord:
        target = str(geometry_id)
        for record in self.records:
            if record.geometry_id == target:
                return record
        raise KeyError(target)


class SiteModelViewerAdapter:
    """Read-only projection consumed by the future CAD/PDF project viewer."""

    def build(self, service: SiteModelService) -> ViewerSnapshot:
        snapshot = service.snapshot()
        records: list[ViewerGeometryRecord] = []
        for geometry in snapshot.geometries:
            annotation = service.resolved_annotation(geometry.geometry_id)
            metadata = dict(geometry.metadata)
            records.append(
                ViewerGeometryRecord(
                    geometry_id=geometry.geometry_id,
                    kind=geometry.kind,
                    points=geometry.points,
                    closed=geometry.closed,
                    source_ref=geometry.source_ref,
                    source_id=str(metadata.get("project_source_id") or ""),
                    source_kind=str(metadata.get("project_source_kind") or ""),
                    source_path=str(metadata.get("project_source_path") or ""),
                    entity_id=str(metadata.get("source_entity_id") or ""),
                    layer=str(metadata.get("source_layer") or ""),
                    page_index=self._page_index(metadata.get("source_page_index")),
                    role=None if annotation is None else annotation.role,
                    annotation_source=None if annotation is None else annotation.source,
                    confidence=None if annotation is None else annotation.confidence,
                    label="" if annotation is None else annotation.label,
                    notes="" if annotation is None else annotation.notes,
                    reason="" if annotation is None else annotation.reason,
                    evidence=() if annotation is None else annotation.evidence,
                    artist_confirmed=False if annotation is None else annotation.artist_confirmed,
                    metadata=metadata,
                )
            )
        return ViewerSnapshot(revision=snapshot.revision, records=tuple(records))

    @staticmethod
    def _page_index(value: Any) -> int | None:
        return None if value is None else int(value)
