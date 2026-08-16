from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class GeometryKind(str, Enum):
    POINT = "point"
    LINE = "line"
    POLYLINE = "polyline"
    REGION = "region"
    HATCH = "hatch"


class SemanticRole(str, Enum):
    UNKNOWN = "unknown"
    FRONT_BOUNDARY = "front_boundary"
    REAR_BOUNDARY = "rear_boundary"
    SIDE_BOUNDARY = "side_boundary"
    SIDEWALK = "sidewalk"
    STREET_EDGE = "street_edge"
    DRIVEWAY = "driveway"
    PARKING = "parking"
    BUILDING_EDGE = "building_edge"
    WALL = "wall"
    PLANTING_BED = "planting_bed"
    LAWN = "lawn"
    SPECIES_ZONE = "species_zone"
    CLUSTER_ZONE = "cluster_zone"
    KEEP_CLEAR = "keep_clear"


class AnnotationSource(str, Enum):
    AI_INFERRED = "ai_inferred"
    ARTIST_CONFIRMED = "artist_confirmed"
    ARTIST_OVERRIDE = "artist_override"


_SOURCE_PRIORITY = {
    AnnotationSource.AI_INFERRED: 10,
    AnnotationSource.ARTIST_CONFIRMED: 20,
    AnnotationSource.ARTIST_OVERRIDE: 30,
}


@dataclass(frozen=True)
class SitePoint:
    x: float
    y: float
    z: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SitePoint":
        return cls(float(payload["x"]), float(payload["y"]), float(payload.get("z", 0.0)))


@dataclass(frozen=True)
class SiteGeometry:
    geometry_id: str
    kind: GeometryKind
    points: tuple[SitePoint, ...]
    closed: bool = False
    source_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.geometry_id).strip():
            raise ValueError("geometry_id must be non-empty")
        if not self.points:
            raise ValueError("site geometry must contain at least one point")
        if self.kind in {GeometryKind.REGION, GeometryKind.HATCH} and len(self.points) < 3:
            raise ValueError(f"{self.kind.value} geometry requires at least three points")

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry_id": self.geometry_id,
            "kind": self.kind.value,
            "points": [point.to_dict() for point in self.points],
            "closed": bool(self.closed),
            "source_ref": self.source_ref,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SiteGeometry":
        return cls(
            geometry_id=str(payload["geometry_id"]),
            kind=GeometryKind(str(payload["kind"])),
            points=tuple(SitePoint.from_dict(item) for item in payload.get("points") or ()),
            closed=bool(payload.get("closed", False)),
            source_ref=str(payload.get("source_ref") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class SemanticAnnotation:
    geometry_id: str
    role: SemanticRole
    source: AnnotationSource
    confidence: float | None = None
    label: str = ""
    notes: str = ""
    reason: str = ""
    evidence: tuple[str, ...] = ()
    revision: int = 1

    def __post_init__(self) -> None:
        if not str(self.geometry_id).strip():
            raise ValueError("annotation geometry_id must be non-empty")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("annotation confidence must be between 0 and 1")
        if int(self.revision) < 1:
            raise ValueError("annotation revision must be positive")

    @property
    def priority(self) -> int:
        return _SOURCE_PRIORITY[self.source]

    @property
    def artist_confirmed(self) -> bool:
        return self.source in {AnnotationSource.ARTIST_CONFIRMED, AnnotationSource.ARTIST_OVERRIDE}

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry_id": self.geometry_id,
            "role": self.role.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "label": self.label,
            "notes": self.notes,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "revision": int(self.revision),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SemanticAnnotation":
        confidence = payload.get("confidence")
        return cls(
            geometry_id=str(payload["geometry_id"]),
            role=SemanticRole(str(payload["role"])),
            source=AnnotationSource(str(payload["source"])),
            confidence=None if confidence is None else float(confidence),
            label=str(payload.get("label") or ""),
            notes=str(payload.get("notes") or ""),
            reason=str(payload.get("reason") or ""),
            evidence=tuple(str(item) for item in payload.get("evidence") or ()),
            revision=int(payload.get("revision", 1)),
        )


@dataclass(frozen=True)
class SiteModelSnapshot:
    version: int
    revision: int
    geometries: tuple[SiteGeometry, ...]
    annotations: tuple[SemanticAnnotation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "revision": int(self.revision),
            "geometries": [item.to_dict() for item in self.geometries],
            "annotations": [item.to_dict() for item in self.annotations],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SiteModelSnapshot":
        return cls(
            version=int(payload.get("version", 1)),
            revision=int(payload.get("revision", 0)),
            geometries=tuple(SiteGeometry.from_dict(item) for item in payload.get("geometries") or ()),
            annotations=tuple(SemanticAnnotation.from_dict(item) for item in payload.get("annotations") or ()),
        )


def normalize_points(points: Iterable[SitePoint | tuple[float, float] | tuple[float, float, float]]) -> tuple[SitePoint, ...]:
    normalized: list[SitePoint] = []
    for point in points:
        if isinstance(point, SitePoint):
            normalized.append(point)
            continue
        if len(point) == 2:
            normalized.append(SitePoint(float(point[0]), float(point[1]), 0.0))
            continue
        if len(point) == 3:
            normalized.append(SitePoint(float(point[0]), float(point[1]), float(point[2])))
            continue
        raise ValueError("point tuples must have two or three values")
    return tuple(normalized)
