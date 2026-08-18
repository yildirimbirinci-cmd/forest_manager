from __future__ import annotations

from dataclasses import dataclass
from math import hypot, sqrt
from typing import Any, Iterable, Mapping, Sequence

from forest_manager.forest_control.spline_world_space import (
    SelectedSplineWorldSpace,
    WorldPoint,
    read_selected_spline_world_space,
)


class SceneSpaceSemanticRegionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class Axis2:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


def _dedupe_ring(points: Iterable[Point2], tolerance: float = 1e-7) -> tuple[Point2, ...]:
    result: list[Point2] = []
    for point in points:
        if result and hypot(point.x - result[-1].x, point.y - result[-1].y) <= tolerance:
            continue
        result.append(point)
    if len(result) >= 2 and hypot(result[0].x - result[-1].x, result[0].y - result[-1].y) <= tolerance:
        result.pop()
    return tuple(result)


def signed_area(points: Sequence[Point2]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y - nxt.x * point.y
    return total * 0.5


def normalize_ccw(points: Iterable[Point2]) -> tuple[Point2, ...]:
    ring = _dedupe_ring(points)
    if len(ring) < 3:
        raise SceneSpaceSemanticRegionError("Boundary polygon requires at least three unique points.")
    area = signed_area(ring)
    if abs(area) <= 1e-9:
        raise SceneSpaceSemanticRegionError("Boundary polygon has near-zero area.")
    return ring if area > 0.0 else tuple(reversed(ring))


def polygon_centroid(points: Sequence[Point2]) -> Point2:
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        cross = point.x * nxt.y - nxt.x * point.y
        area2 += cross
        cx += (point.x + nxt.x) * cross
        cy += (point.y + nxt.y) * cross
    if abs(area2) <= 1e-12:
        raise SceneSpaceSemanticRegionError("Cannot compute centroid for degenerate polygon.")
    return Point2(cx / (3.0 * area2), cy / (3.0 * area2))


def _normalize_axis(x: float, y: float) -> Axis2:
    length = hypot(x, y)
    if length <= 1e-12:
        raise SceneSpaceSemanticRegionError("Direction vector must be non-zero.")
    return Axis2(x / length, y / length)


def _minor_principal_axis(points: Sequence[Point2], centroid: Point2) -> Axis2:
    xx = yy = xy = 0.0
    for point in points:
        dx = point.x - centroid.x
        dy = point.y - centroid.y
        xx += dx * dx
        yy += dy * dy
        xy += dx * dy
    count = float(len(points))
    xx /= count
    yy /= count
    xy /= count

    trace = xx + yy
    delta = sqrt(max(0.0, (xx - yy) * (xx - yy) + 4.0 * xy * xy))
    minor_lambda = (trace - delta) * 0.5

    # Eigenvector for the minor eigenvalue. Choose the numerically stable form.
    if abs(xy) > abs(xx - minor_lambda):
        axis = _normalize_axis(1.0, -(xx - minor_lambda) / xy)
    elif abs(xy) > 1e-12:
        axis = _normalize_axis(-(yy - minor_lambda) / xy, 1.0)
    else:
        axis = Axis2(1.0, 0.0) if xx <= yy else Axis2(0.0, 1.0)

    # Deterministic sign only. This is not a claim about site frontage.
    if axis.y < -1e-12 or (abs(axis.y) <= 1e-12 and axis.x < 0.0):
        axis = Axis2(-axis.x, -axis.y)
    return axis


def _projection(point: Point2, origin: Point2, axis: Axis2) -> float:
    return (point.x - origin.x) * axis.x + (point.y - origin.y) * axis.y


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


def _validate_ratios(ratios: Sequence[float]) -> tuple[float, float, float]:
    if len(ratios) != 3:
        raise ValueError("Exactly three semantic band ratios are required.")
    values = tuple(float(value) for value in ratios)
    if any(value <= 0.0 for value in values):
        raise ValueError("Semantic band ratios must be positive.")
    total = sum(values)
    return tuple(value / total for value in values)  # type: ignore[return-value]


def build_semantic_region_plan(
    geometry: SelectedSplineWorldSpace,
    *,
    front_hint_world_xy: tuple[float, float] | None = None,
    band_ratios: Sequence[float] = (0.32, 0.36, 0.32),
) -> dict[str, Any]:
    if geometry.spline_count != 1:
        raise SceneSpaceSemanticRegionError(
            "Stage 8 semantic region foundation currently requires exactly one closed planting spline."
        )
    spline = geometry.splines[0]
    source_points = spline.samples if len(spline.samples) >= 8 else spline.knots
    polygon = normalize_ccw(Point2(point.x, point.y) for point in source_points)
    centroid = polygon_centroid(polygon)
    area_system_units2 = signed_area(polygon)

    if front_hint_world_xy is not None:
        # Hint points from site centroid toward the front. Depth axis is front -> back.
        front = _normalize_axis(float(front_hint_world_xy[0]), float(front_hint_world_xy[1]))
        depth_axis = Axis2(-front.x, -front.y)
        orientation_source = "explicit_front_hint"
        site_front_confirmed = True
    else:
        depth_axis = _minor_principal_axis(polygon, centroid)
        orientation_source = "deterministic_minor_geometry_axis"
        site_front_confirmed = False

    projections = [_projection(point, centroid, depth_axis) for point in polygon]
    low = min(projections)
    high = max(projections)
    span = high - low
    if span <= 1e-9:
        raise SceneSpaceSemanticRegionError("Boundary has no usable scene-space depth span.")

    foreground_ratio, midground_ratio, background_ratio = _validate_ratios(band_ratios)
    cut1 = low + span * foreground_ratio
    cut2 = cut1 + span * midground_ratio

    region_specs = (
        ("foreground", low, cut1, 0.0, foreground_ratio),
        ("midground", cut1, cut2, foreground_ratio, foreground_ratio + midground_ratio),
        ("background", cut2, high, foreground_ratio + midground_ratio, 1.0),
    )

    regions = []
    for name, minimum, maximum, normalized_minimum, normalized_maximum in region_specs:
        regions.append(
            {
                "region_id": f"scene_region:{name}",
                "semantic_role": name,
                "constraint_type": "site_polygon_intersection_with_depth_projection_interval",
                "depth_projection_system_units": {"min": minimum, "max": maximum},
                "normalized_depth_interval": {
                    "min": normalized_minimum,
                    "max": normalized_maximum,
                },
                "inside_site_polygon_required": True,
                "reference_image_coordinates_used": False,
            }
        )

    one_meter = float((geometry.scene_units or {}).get("one_meter_system_units") or 0.0)
    area_m2 = None
    if one_meter > 0.0:
        area_m2 = area_system_units2 / (one_meter * one_meter)

    return {
        "verified": True,
        "node_name": geometry.node_name,
        "coordinate_system": "world",
        "scene_units": dict(geometry.scene_units),
        "site_polygon": {
            "source": "selected_3ds_max_spline_world_samples",
            "sample_count": len(polygon),
            "winding": "ccw",
            "points_world_xy": [point.as_dict() for point in polygon],
            "area_system_units2": area_system_units2,
            "area_m2": area_m2,
            "centroid_world_xy": centroid.as_dict(),
        },
        "semantic_depth_axis_world_xy": depth_axis.as_dict(),
        "orientation_source": orientation_source,
        "site_front_confirmed": site_front_confirmed,
        "regions": regions,
        "reference_image_role": "semantic_composition_guidance_only",
        "reference_image_coordinates_used": False,
        "forest_pack_mutated": False,
        "map_policy": "parked_not_projected_from_reference_image",
    }


def build_selected_boundary_semantic_region_plan(
    *,
    samples_per_spline: int = 64,
    front_hint_world_xy: tuple[float, float] | None = None,
    band_ratios: Sequence[float] = (0.32, 0.36, 0.32),
    preflight: bool = True,
) -> dict[str, Any]:
    geometry = read_selected_spline_world_space(
        samples_per_spline=samples_per_spline,
        preflight=preflight,
    )
    return build_semantic_region_plan(
        geometry,
        front_hint_world_xy=front_hint_world_xy,
        band_ratios=band_ratios,
    )
