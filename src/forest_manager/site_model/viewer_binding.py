from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .schema import AnnotationSource, GeometryKind, SemanticRole, SitePoint
from .service import SiteModelService
from .viewer import SiteModelViewerAdapter, ViewerGeometryRecord
from .viewer_interaction import SiteModelViewerInteraction


@dataclass(frozen=True)
class ViewerBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class ViewerRenderRecord:
    geometry_id: str
    kind: GeometryKind
    points: tuple[SitePoint, ...]
    closed: bool
    role: SemanticRole | None
    annotation_source: AnnotationSource | None
    confidence: float | None
    artist_confirmed: bool
    label: str
    notes: str
    source_id: str
    source_kind: str
    source_path: str
    layer: str
    page_index: int | None
    selected: bool
    active: bool
    bounds: ViewerBounds


@dataclass(frozen=True)
class ViewerBindingSnapshot:
    revision: int
    records: tuple[ViewerRenderRecord, ...]
    bounds: ViewerBounds | None
    source_ids: tuple[str, ...] = ()
    layers: tuple[str, ...] = ()
    page_indexes: tuple[int, ...] = ()


class SiteModelViewerBinding:
    """Bind Site Model geometry and viewer selection to a render-ready snapshot."""

    def __init__(self, *, adapter: SiteModelViewerAdapter | None = None) -> None:
        self.adapter = adapter or SiteModelViewerAdapter()

    def build(
        self,
        service: SiteModelService,
        *,
        interaction: SiteModelViewerInteraction | None = None,
        source_id: str | None = None,
        page_index: int | None = None,
        layers: Iterable[str] | None = None,
        roles: Iterable[SemanticRole | str] | None = None,
        annotation_sources: Iterable[AnnotationSource | str] | None = None,
    ) -> ViewerBindingSnapshot:
        snapshot = self.adapter.build(service)
        selected = set(() if interaction is None else interaction.selection.geometry_ids)
        active = None if interaction is None else interaction.selection.active_geometry_id
        layer_filter = None if layers is None else {str(item) for item in layers}
        role_filter = None if roles is None else {
            item if isinstance(item, SemanticRole) else SemanticRole(str(item)) for item in roles
        }
        source_filter = None if annotation_sources is None else {
            item if isinstance(item, AnnotationSource) else AnnotationSource(str(item)) for item in annotation_sources
        }

        all_source_ids = tuple(sorted({record.source_id for record in snapshot.records if record.source_id}))
        source_records = [
            record for record in snapshot.records
            if source_id is None or record.source_id == str(source_id)
        ]
        available_layers = tuple(sorted({record.layer for record in source_records if record.layer}))
        available_pages = tuple(sorted({record.page_index for record in source_records if record.page_index is not None}))

        records: list[ViewerRenderRecord] = []
        for record in source_records:
            if page_index is not None and record.page_index != int(page_index):
                continue
            if layer_filter is not None and record.layer not in layer_filter:
                continue
            if role_filter is not None and record.role not in role_filter:
                continue
            if source_filter is not None and record.annotation_source not in source_filter:
                continue
            bounds = self._record_bounds(record)
            records.append(
                ViewerRenderRecord(
                    geometry_id=record.geometry_id,
                    kind=record.kind,
                    points=record.points,
                    closed=record.closed,
                    role=record.role,
                    annotation_source=record.annotation_source,
                    confidence=record.confidence,
                    artist_confirmed=record.artist_confirmed,
                    label=record.label,
                    notes=record.notes,
                    source_id=record.source_id,
                    source_kind=record.source_kind,
                    source_path=record.source_path,
                    layer=record.layer,
                    page_index=record.page_index,
                    selected=record.geometry_id in selected,
                    active=record.geometry_id == active,
                    bounds=bounds,
                )
            )
        return ViewerBindingSnapshot(
            revision=snapshot.revision,
            records=tuple(records),
            bounds=self._combined_bounds(record.bounds for record in records),
            source_ids=all_source_ids,
            layers=available_layers,
            page_indexes=available_pages,
        )

    @staticmethod
    def _record_bounds(record: ViewerGeometryRecord) -> ViewerBounds:
        xs = [point.x for point in record.points]
        ys = [point.y for point in record.points]
        return ViewerBounds(min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _combined_bounds(bounds: Iterable[ViewerBounds]) -> ViewerBounds | None:
        values = tuple(bounds)
        if not values:
            return None
        return ViewerBounds(
            min(item.min_x for item in values),
            min(item.min_y for item in values),
            max(item.max_x for item in values),
            max(item.max_y for item in values),
        )
