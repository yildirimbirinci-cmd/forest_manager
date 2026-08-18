from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


class WallEdgeZoneGeometryError(RuntimeError):
    pass


_EPS = 1e-7


def _point_from_mapping(value: Mapping[str, Any]) -> Point2:
    return Point2(float(value["x"]), float(value["y"]))


def _signed_area(points: Sequence[Point2]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y - nxt.x * point.y
    return total * 0.5


def _polygon_area(points: Sequence[Point2]) -> float:
    return abs(_signed_area(points))


def _is_convex(points: Sequence[Point2]) -> bool:
    if len(points) < 3:
        return False
    sign = 0
    for index in range(len(points)):
        a = points[index]
        b = points[(index + 1) % len(points)]
        c = points[(index + 2) % len(points)]
        cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
        if abs(cross) <= _EPS:
            continue
        current = 1 if cross > 0.0 else -1
        if sign and current != sign:
            return False
        sign = current
    return sign != 0


def _dot_from_edge(point: Point2, start: Point2, normal: Point2) -> float:
    return (point.x - start.x) * normal.x + (point.y - start.y) * normal.y


def _interpolate(a: Point2, b: Point2, t: float) -> Point2:
    return Point2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def _clip_by_signed_distance(
    polygon: Sequence[Point2],
    *,
    start: Point2,
    inward_normal: Point2,
    threshold: float,
    keep_greater_equal: bool,
) -> tuple[Point2, ...]:
    """Clip a polygon against one edge-distance half-plane.

    Signed distance is measured from the boundary edge along its inward normal.
    For a convex planting boundary, distance >= N creates the inward offset side;
    distance <= N creates the edge band side. No rasterization is involved.
    """
    if len(polygon) < 3:
        return ()

    def value(point: Point2) -> float:
        return _dot_from_edge(point, start, inward_normal) - threshold

    def inside(v: float) -> bool:
        return v >= -_EPS if keep_greater_equal else v <= _EPS

    result: list[Point2] = []
    previous = polygon[-1]
    previous_value = value(previous)
    previous_inside = inside(previous_value)
    for current in polygon:
        current_value = value(current)
        current_inside = inside(current_value)
        if current_inside != previous_inside:
            denom = previous_value - current_value
            if abs(denom) > _EPS:
                t = previous_value / denom
                result.append(_interpolate(previous, current, t))
        if current_inside:
            result.append(current)
        previous = current
        previous_value = current_value
        previous_inside = current_inside

    cleaned: list[Point2] = []
    for point in result:
        if not cleaned or abs(point.x - cleaned[-1].x) > _EPS or abs(point.y - cleaned[-1].y) > _EPS:
            cleaned.append(point)
    if len(cleaned) >= 2:
        if abs(cleaned[0].x - cleaned[-1].x) <= _EPS and abs(cleaned[0].y - cleaned[-1].y) <= _EPS:
            cleaned.pop()
    return tuple(cleaned) if len(cleaned) >= 3 else ()


def _segment_records(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [dict(item) for item in (plan.get("segments") or [])]
    if not records:
        raise WallEdgeZoneGeometryError("Wall Edge zone plan has no segment records.")
    return records


def _clip_beyond_segments(
    polygon: Sequence[Point2],
    segments: Iterable[Mapping[str, Any]],
    distance_system_units: float,
) -> tuple[Point2, ...]:
    result = tuple(polygon)
    for segment in segments:
        result = _clip_by_signed_distance(
            result,
            start=_point_from_mapping(segment["start_world_xy"]),
            inward_normal=_point_from_mapping(segment["inward_normal_world_xy"]),
            threshold=distance_system_units,
            keep_greater_equal=True,
        )
        if not result:
            break
    return result


def _edge_band_part(
    boundary: Sequence[Point2],
    segment: Mapping[str, Any],
    distance_system_units: float,
    *,
    exclude_segments: Iterable[Mapping[str, Any]] = (),
    exclude_distance_system_units: float = 0.0,
) -> tuple[Point2, ...]:
    result = _clip_by_signed_distance(
        boundary,
        start=_point_from_mapping(segment["start_world_xy"]),
        inward_normal=_point_from_mapping(segment["inward_normal_world_xy"]),
        threshold=distance_system_units,
        keep_greater_equal=False,
    )
    for excluded in exclude_segments:
        result = _clip_by_signed_distance(
            result,
            start=_point_from_mapping(excluded["start_world_xy"]),
            inward_normal=_point_from_mapping(excluded["inward_normal_world_xy"]),
            threshold=exclude_distance_system_units,
            keep_greater_equal=True,
        )
        if not result:
            break
    return result


def _payload(points: Sequence[Point2], one_meter_system_units: float) -> dict[str, Any]:
    area_system = _polygon_area(points)
    return {
        "points_world_xy": [point.as_dict() for point in points],
        "vertex_count": len(points),
        "area_system_units_squared": area_system,
        "area_square_meters": area_system / (one_meter_system_units * one_meter_system_units),
    }


def build_wall_edge_zone_geometry(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize vector sub-region polygons from an artist Wall Edge plan.

    Stage 8 currently fails closed on non-convex boundaries. This is deliberate:
    the geometry result is intended to become Forest Pack Area input, so an
    approximate or self-intersecting polygon must never be silently accepted.
    Curved/non-convex support can be added later using sampled spline topology.
    """
    if not bool(plan.get("verified")):
        raise WallEdgeZoneGeometryError("Wall Edge zone plan is not verified.")
    boundary = tuple(_point_from_mapping(item) for item in (plan.get("boundary_polygon_world_xy") or []))
    if len(boundary) < 3:
        raise WallEdgeZoneGeometryError("Wall Edge zone plan has fewer than three boundary points.")
    if not _is_convex(boundary):
        raise WallEdgeZoneGeometryError(
            "Current vector-zone geometry foundation requires a convex closed boundary; refusing approximate geometry."
        )

    one_meter = float(((plan.get("scene_units") or {}).get("one_meter_system_units")) or 0.0)
    if not isfinite(one_meter) or one_meter <= 0.0:
        raise WallEdgeZoneGeometryError("Scene unit payload does not provide one_meter_system_units.")

    segments = _segment_records(plan)
    wall_segments = [item for item in segments if item.get("role") == "wall_edge"]
    walkway_segments = [item for item in segments if item.get("role") == "walkway_open_edge"]
    if not wall_segments:
        raise WallEdgeZoneGeometryError("At least one artist Wall Edge segment is required.")

    zones = plan.get("zones") or {}
    wall_distance = float(((zones.get("wall_band") or {}).get("distance_system_units")) or 0.0)
    walkway_distance = float(((zones.get("walkway_band") or {}).get("distance_system_units")) or 0.0)
    if wall_distance <= 0.0 or walkway_distance <= 0.0:
        raise WallEdgeZoneGeometryError("Wall/walkway vector zone distances must be positive.")

    wall_parts = [
        _edge_band_part(boundary, segment, wall_distance)
        for segment in wall_segments
    ]
    wall_parts = [item for item in wall_parts if item]

    # Artist wall context is authoritative: walkway parts are clipped beyond every
    # wall band so the two semantic roles do not overlap at wall corners.
    walkway_parts = [
        _edge_band_part(
            boundary,
            segment,
            walkway_distance,
            exclude_segments=wall_segments,
            exclude_distance_system_units=wall_distance,
        )
        for segment in walkway_segments
    ]
    walkway_parts = [item for item in walkway_parts if item]

    interior = _clip_beyond_segments(boundary, wall_segments, wall_distance)
    interior = _clip_beyond_segments(interior, walkway_segments, walkway_distance)

    result = {
        "verified": bool(wall_parts) and bool(interior),
        "node_name": plan.get("node_name"),
        "spline_index": plan.get("spline_index"),
        "coordinate_system": "world_xy",
        "geometry_model": "convex_vector_half_plane_clipping",
        "boundary": _payload(boundary, one_meter),
        "wall_band": {
            "priority": 100,
            "parts": [_payload(item, one_meter) for item in wall_parts],
        },
        "walkway_band": {
            "priority": 50,
            "parts": [_payload(item, one_meter) for item in walkway_parts],
        },
        "interior": {
            "priority": 10,
            "parts": [_payload(interior, one_meter)] if interior else [],
        },
        "wall_segments": [int(item["segment_index"]) for item in wall_segments],
        "walkway_open_segments": [int(item["segment_index"]) for item in walkway_segments],
        "distribution_map_used": False,
        "reference_image_coordinates_used": False,
        "forest_pack_mutated": False,
    }
    if not result["verified"]:
        raise WallEdgeZoneGeometryError("Vector zone clipping produced no usable wall or interior polygon.")
    return result
