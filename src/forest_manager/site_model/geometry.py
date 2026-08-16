from __future__ import annotations

from typing import Iterable

from .schema import GeometryKind, SiteGeometry, SitePoint, normalize_points


def create_geometry(
    geometry_id: str,
    kind: GeometryKind | str,
    points: Iterable[SitePoint | tuple[float, float] | tuple[float, float, float]],
    *,
    closed: bool = False,
    source_ref: str = "",
    metadata: dict | None = None,
) -> SiteGeometry:
    geometry_kind = kind if isinstance(kind, GeometryKind) else GeometryKind(str(kind))
    return SiteGeometry(
        geometry_id=str(geometry_id),
        kind=geometry_kind,
        points=normalize_points(points),
        closed=bool(closed),
        source_ref=str(source_ref),
        metadata=dict(metadata or {}),
    )
