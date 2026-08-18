from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Iterable, Sequence

from forest_manager.forest_control.spline_world_space import SelectedSplineWorldSpace, WorldPoint
from forest_manager.forest_control.wall_edge_annotations import WallEdgeAnnotation


class WallEdgeZonePlanError(RuntimeError):
    pass


@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class Segment2:
    segment_index: int
    role: str
    start: Point2
    end: Point2
    inward_normal: Point2
    length_system_units: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "role": self.role,
            "start_world_xy": self.start.as_dict(),
            "end_world_xy": self.end.as_dict(),
            "inward_normal_world_xy": self.inward_normal.as_dict(),
            "length_system_units": self.length_system_units,
        }


def _signed_area(points: Sequence[Point2]) -> float:
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y - nxt.x * point.y
    return total * 0.5


def _normalize(x: float, y: float) -> Point2:
    length = hypot(x, y)
    if length <= 1e-9:
        raise WallEdgeZonePlanError("Planting boundary contains a zero-length segment.")
    return Point2(x / length, y / length)


def _point2(point: WorldPoint) -> Point2:
    return Point2(float(point.x), float(point.y))


def _segment_distance(point: Point2, segment: Segment2) -> float:
    ax, ay = segment.start.x, segment.start.y
    bx, by = segment.end.x, segment.end.y
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return hypot(point.x - ax, point.y - ay)
    t = ((point.x - ax) * dx + (point.y - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    px, py = ax + t * dx, ay + t * dy
    return hypot(point.x - px, point.y - py)


def point_in_polygon(point: Point2, polygon: Sequence[Point2]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        pj = polygon[j]
        intersects = ((pi.y > point.y) != (pj.y > point.y)) and (
            point.x < (pj.x - pi.x) * (point.y - pi.y) / ((pj.y - pi.y) or 1e-300) + pi.x
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def classify_point(
    point: Point2,
    *,
    polygon: Sequence[Point2],
    segments: Sequence[Segment2],
    wall_band_system_units: float,
    walkway_band_system_units: float,
) -> str:
    """Classify a scene-space point without any raster/distribution map.

    Wall has priority where edge-distance bands overlap. This keeps artist-marked
    wall context authoritative. Points outside the planting polygon are rejected.
    """
    if not point_in_polygon(point, polygon):
        return "outside"
    wall = [s for s in segments if s.role == "wall_edge"]
    walkway = [s for s in segments if s.role == "walkway_open_edge"]
    if wall and min(_segment_distance(point, s) for s in wall) <= wall_band_system_units:
        return "wall_band"
    if walkway and min(_segment_distance(point, s) for s in walkway) <= walkway_band_system_units:
        return "walkway_band"
    return "interior"


def build_wall_edge_zone_plan(
    geometry: SelectedSplineWorldSpace,
    annotation: WallEdgeAnnotation,
    *,
    wall_band_meters: float,
    walkway_band_meters: float,
) -> dict[str, Any]:
    if geometry.node_name != annotation.node_name:
        raise WallEdgeZonePlanError(
            f"Wall Edge annotation belongs to {annotation.node_name}, selected boundary is {geometry.node_name}."
        )
    if geometry.spline_count != 1 or len(geometry.splines) != 1:
        raise WallEdgeZonePlanError("Wall Edge zone planning currently requires one closed spline per Line.")
    spline = geometry.splines[0]
    if not spline.closed:
        raise WallEdgeZonePlanError("Planting boundary must be closed.")
    if annotation.spline_index != spline.spline_index:
        raise WallEdgeZonePlanError("Wall Edge annotation spline index does not match selected geometry.")
    if len(spline.knots) != annotation.segment_count:
        raise WallEdgeZonePlanError(
            "Wall Edge annotation segment count no longer matches the selected Line. Re-mark Wall Edge after editing the spline."
        )

    wall_band_meters = float(wall_band_meters)
    walkway_band_meters = float(walkway_band_meters)
    if wall_band_meters <= 0.0 or walkway_band_meters <= 0.0:
        raise WallEdgeZonePlanError("Wall and walkway band distances must be positive.")

    one_meter = float((geometry.scene_units or {}).get("one_meter_system_units") or 0.0)
    if one_meter <= 0.0:
        raise WallEdgeZonePlanError("Scene unit payload does not provide one_meter_system_units.")

    polygon = tuple(_point2(point) for point in spline.knots)
    area = _signed_area(polygon)
    if abs(area) <= 1e-9:
        raise WallEdgeZonePlanError("Planting boundary has near-zero projected area.")
    ccw = area > 0.0

    segments: list[Segment2] = []
    wall_set = set(annotation.wall_segments)
    for zero_index, start in enumerate(polygon):
        end = polygon[(zero_index + 1) % len(polygon)]
        dx, dy = end.x - start.x, end.y - start.y
        direction = _normalize(dx, dy)
        normal = Point2(-direction.y, direction.x) if ccw else Point2(direction.y, -direction.x)
        segment_index = zero_index + 1
        role = "wall_edge" if segment_index in wall_set else "walkway_open_edge"
        segments.append(
            Segment2(
                segment_index=segment_index,
                role=role,
                start=start,
                end=end,
                inward_normal=normal,
                length_system_units=hypot(dx, dy),
            )
        )

    wall_band_system = wall_band_meters * one_meter
    walkway_band_system = walkway_band_meters * one_meter
    return {
        "verified": True,
        "node_name": geometry.node_name,
        "spline_index": spline.spline_index,
        "coordinate_system": "world_xy",
        "scene_units": dict(geometry.scene_units),
        "polygon_winding": "ccw" if ccw else "cw",
        "boundary_polygon_world_xy": [point.as_dict() for point in polygon],
        "segments": [segment.as_dict() for segment in segments],
        "roles": {
            "wall_segments": list(annotation.wall_segments),
            "walkway_open_segments": list(annotation.walkway_open_segments),
            "unmarked_boundary_default": "walkway_open_edge",
        },
        "zones": {
            "wall_band": {
                "constraint": "inside_boundary_and_distance_to_artist_wall_edge",
                "distance_meters": wall_band_meters,
                "distance_system_units": wall_band_system,
                "priority": 100,
            },
            "walkway_band": {
                "constraint": "inside_boundary_and_distance_to_unmarked_boundary_edge",
                "distance_meters": walkway_band_meters,
                "distance_system_units": walkway_band_system,
                "priority": 50,
            },
            "interior": {
                "constraint": "inside_boundary_minus_edge_distance_bands",
                "priority": 10,
            },
        },
        "wall_edge_source": "artist_3ds_max_segment_selection",
        "reference_image_coordinates_used": False,
        "distribution_map_used": False,
        "forest_pack_mutated": False,
    }
