from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .ingestion import ImportBatch, ImportedEntity, ProjectSource, ProjectSourceKind
from .schema import GeometryKind, SemanticRole


class ParserAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPrimitive:
    entity_id: str
    primitive_type: str
    points: tuple[tuple[float, ...], ...]
    closed: bool = False
    layer: str = ""
    page_index: int | None = None
    semantic_role: str | None = None
    semantic_confidence: float | None = None
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


_TYPE_ALIASES = {
    "point": GeometryKind.POINT,
    "line": GeometryKind.LINE,
    "polyline": GeometryKind.POLYLINE,
    "lwpolyline": GeometryKind.POLYLINE,
    "path": GeometryKind.POLYLINE,
    "polygon": GeometryKind.REGION,
    "region": GeometryKind.REGION,
    "hatch": GeometryKind.HATCH,
}


def _normalize_kind(raw: str, *, closed: bool) -> GeometryKind:
    key = str(raw or "").strip().lower()
    try:
        kind = _TYPE_ALIASES[key]
    except KeyError as exc:
        raise ParserAdapterError(f"unsupported parser primitive type: {raw}") from exc
    if key == "path" and closed:
        return GeometryKind.REGION
    return kind


def _as_points(value: Any) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ParserAdapterError("parser primitive points must be a non-empty sequence")
    points: list[tuple[float, ...]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) not in {2, 3}:
            raise ParserAdapterError("parser points must contain two or three numeric values")
        try:
            points.append(tuple(float(part) for part in item))
        except (TypeError, ValueError) as exc:
            raise ParserAdapterError("parser point coordinates must be numeric") from exc
    return tuple(points)


def _primitive_from_mapping(payload: Mapping[str, Any]) -> ParsedPrimitive:
    entity_id = str(payload.get("entity_id") or payload.get("handle") or payload.get("id") or "").strip()
    if not entity_id:
        raise ParserAdapterError("parser primitive requires entity_id, handle, or id")
    primitive_type = str(payload.get("primitive_type") or payload.get("type") or "").strip()
    if not primitive_type:
        raise ParserAdapterError("parser primitive requires primitive_type or type")
    page_raw = payload.get("page_index")
    return ParsedPrimitive(
        entity_id=entity_id,
        primitive_type=primitive_type,
        points=_as_points(payload.get("points") or payload.get("vertices")),
        closed=bool(payload.get("closed", False)),
        layer=str(payload.get("layer") or ""),
        page_index=None if page_raw is None else int(page_raw),
        semantic_role=None if payload.get("semantic_role") is None else str(payload.get("semantic_role")),
        semantic_confidence=None if payload.get("semantic_confidence") is None else float(payload.get("semantic_confidence")),
        label=str(payload.get("label") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


class _BaseParserAdapter:
    source_kind: ProjectSourceKind

    def adapt(
        self,
        source: ProjectSource,
        primitives: Iterable[ParsedPrimitive | Mapping[str, Any]],
    ) -> ImportBatch:
        if source.kind is not self.source_kind:
            raise ParserAdapterError(
                f"{type(self).__name__} requires a {self.source_kind.value} project source"
            )
        entities: list[ImportedEntity] = []
        for raw in primitives:
            primitive = raw if isinstance(raw, ParsedPrimitive) else _primitive_from_mapping(raw)
            self._validate(source, primitive)
            kind = _normalize_kind(primitive.primitive_type, closed=primitive.closed)
            role = None if primitive.semantic_role is None else SemanticRole(primitive.semantic_role)
            metadata = dict(primitive.metadata)
            metadata.setdefault("parser_primitive_type", primitive.primitive_type)
            entities.append(
                ImportedEntity.create(
                    source_id=source.source_id,
                    entity_id=primitive.entity_id,
                    kind=kind,
                    points=primitive.points,
                    closed=primitive.closed,
                    layer=primitive.layer,
                    page_index=primitive.page_index,
                    semantic_role=role,
                    semantic_confidence=primitive.semantic_confidence,
                    label=primitive.label,
                    metadata=metadata,
                )
            )
        return ImportBatch(source=source, entities=tuple(entities))

    def _validate(self, source: ProjectSource, primitive: ParsedPrimitive) -> None:
        del source, primitive


class CadParserAdapter(_BaseParserAdapter):
    """Convert CAD parser output (DXF/DWG extraction) to an ImportBatch."""

    source_kind = ProjectSourceKind.CAD

    def _validate(self, source: ProjectSource, primitive: ParsedPrimitive) -> None:
        del source
        if primitive.page_index is not None:
            raise ParserAdapterError("CAD primitives must not declare page_index")


class PdfParserAdapter(_BaseParserAdapter):
    """Convert vector/PDF parser output to an ImportBatch with page identity."""

    source_kind = ProjectSourceKind.PDF

    def _validate(self, source: ProjectSource, primitive: ParsedPrimitive) -> None:
        if primitive.page_index is None:
            raise ParserAdapterError("PDF primitives require page_index")
        if primitive.page_index < 0:
            raise ParserAdapterError("PDF page_index must be zero or greater")
        if source.page_count is not None and primitive.page_index >= source.page_count:
            raise ParserAdapterError("PDF page_index is outside project source page_count")
