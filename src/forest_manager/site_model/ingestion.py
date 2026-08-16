from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePath
from typing import Any, Iterable

from .annotations import make_ai_annotation
from .geometry import create_geometry
from .schema import GeometryKind, SemanticAnnotation, SemanticRole, SitePoint, normalize_points
from .service import SiteModelError, SiteModelService


class ProjectSourceKind(str, Enum):
    CAD = "cad"
    PDF = "pdf"


@dataclass(frozen=True)
class ProjectSource:
    source_id: str
    kind: ProjectSourceKind
    path: str
    page_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.source_id).strip():
            raise ValueError("source_id must be non-empty")
        if not str(self.path).strip():
            raise ValueError("source path must be non-empty")
        if self.page_count is not None and int(self.page_count) < 1:
            raise ValueError("page_count must be positive when provided")

    @property
    def display_name(self) -> str:
        return PurePath(self.path).name or self.path


@dataclass(frozen=True)
class SourceLocator:
    source_id: str
    entity_id: str
    layer: str = ""
    page_index: int | None = None

    def __post_init__(self) -> None:
        if not str(self.source_id).strip():
            raise ValueError("locator source_id must be non-empty")
        if not str(self.entity_id).strip():
            raise ValueError("locator entity_id must be non-empty")
        if self.page_index is not None and int(self.page_index) < 0:
            raise ValueError("page_index must be zero or greater")

    @property
    def stable_key(self) -> str:
        page = "" if self.page_index is None else f":p{int(self.page_index)}"
        return f"{self.source_id}{page}:{self.entity_id}"


@dataclass(frozen=True)
class ImportedEntity:
    locator: SourceLocator
    kind: GeometryKind
    points: tuple[SitePoint, ...]
    closed: bool = False
    semantic_role: SemanticRole | None = None
    semantic_confidence: float | None = None
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("imported entity must contain at least one point")
        if self.semantic_confidence is not None and not 0.0 <= float(self.semantic_confidence) <= 1.0:
            raise ValueError("semantic_confidence must be between 0 and 1")

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        entity_id: str,
        kind: GeometryKind | str,
        points: Iterable[SitePoint | tuple[float, float] | tuple[float, float, float]],
        closed: bool = False,
        layer: str = "",
        page_index: int | None = None,
        semantic_role: SemanticRole | str | None = None,
        semantic_confidence: float | None = None,
        label: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "ImportedEntity":
        role = None if semantic_role is None else (
            semantic_role if isinstance(semantic_role, SemanticRole) else SemanticRole(str(semantic_role))
        )
        geometry_kind = kind if isinstance(kind, GeometryKind) else GeometryKind(str(kind))
        return cls(
            locator=SourceLocator(
                source_id=str(source_id),
                entity_id=str(entity_id),
                layer=str(layer),
                page_index=page_index,
            ),
            kind=geometry_kind,
            points=normalize_points(points),
            closed=bool(closed),
            semantic_role=role,
            semantic_confidence=semantic_confidence,
            label=str(label),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class ImportBatch:
    source: ProjectSource
    entities: tuple[ImportedEntity, ...]

    def __post_init__(self) -> None:
        entity_ids: set[str] = set()
        for entity in self.entities:
            if entity.locator.source_id != self.source.source_id:
                raise ValueError("entity source_id does not match import source")
            stable_key = entity.locator.stable_key
            if stable_key in entity_ids:
                raise ValueError(f"duplicate imported entity: {stable_key}")
            entity_ids.add(stable_key)


@dataclass(frozen=True)
class IngestionResult:
    source_id: str
    geometry_ids: tuple[str, ...]
    ai_annotation_ids: tuple[str, ...]


class SiteModelIngestor:
    """Parser-independent CAD/PDF ingestion adapter for the Stage 8 site model."""

    def geometry_id_for(self, source: ProjectSource, entity: ImportedEntity) -> str:
        if entity.locator.source_id != source.source_id:
            raise SiteModelError("cannot map entity from a different source")
        return f"{source.kind.value}:{entity.locator.stable_key}"

    def ingest(self, service: SiteModelService, batch: ImportBatch) -> IngestionResult:
        geometry_ids: list[str] = []
        ai_annotations: list[SemanticAnnotation] = []

        for entity in batch.entities:
            geometry_id = self.geometry_id_for(batch.source, entity)
            source_ref = self._source_ref(batch.source, entity.locator)
            metadata = dict(entity.metadata)
            metadata.update(
                {
                    "project_source_id": batch.source.source_id,
                    "project_source_kind": batch.source.kind.value,
                    "project_source_path": batch.source.path,
                    "source_entity_id": entity.locator.entity_id,
                    "source_layer": entity.locator.layer,
                    "source_page_index": entity.locator.page_index,
                }
            )
            service.upsert_geometry(
                create_geometry(
                    geometry_id,
                    entity.kind,
                    entity.points,
                    closed=entity.closed,
                    source_ref=source_ref,
                    metadata=metadata,
                )
            )
            geometry_ids.append(geometry_id)

            if entity.semantic_role is not None:
                ai_annotations.append(
                    make_ai_annotation(
                        geometry_id,
                        entity.semantic_role,
                        confidence=entity.semantic_confidence,
                        label=entity.label,
                        notes=f"Imported semantic candidate from {batch.source.kind.value.upper()} source",
                    )
                )

        if ai_annotations:
            service.reanalyze_ai(ai_annotations)

        return IngestionResult(
            source_id=batch.source.source_id,
            geometry_ids=tuple(geometry_ids),
            ai_annotation_ids=tuple(item.geometry_id for item in ai_annotations),
        )

    @staticmethod
    def _source_ref(source: ProjectSource, locator: SourceLocator) -> str:
        fragments = [f"entity={locator.entity_id}"]
        if locator.layer:
            fragments.append(f"layer={locator.layer}")
        if locator.page_index is not None:
            fragments.append(f"page={int(locator.page_index)}")
        return f"{source.path}#{'&'.join(fragments)}"
