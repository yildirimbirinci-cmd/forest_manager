from __future__ import annotations

from forest_manager.forest_control.spline_world_space import SelectedSplineWorldSpace, WorldPoint, WorldSpline
from forest_manager.forest_control.wall_edge_annotations import WallEdgeAnnotation
from forest_manager.forest_control.wall_edge_zone_plan import Point2, Segment2, build_wall_edge_zone_plan, classify_point


def _geometry() -> SelectedSplineWorldSpace:
    knots = (
        WorldPoint(0.0, 0.0, 0.0),
        WorldPoint(1000.0, 0.0, 0.0),
        WorldPoint(1000.0, 500.0, 0.0),
        WorldPoint(0.0, 500.0, 0.0),
    )
    return SelectedSplineWorldSpace(
        node_name="Line001",
        node_class="Line",
        coordinate_system="world",
        spline_count=1,
        samples_per_spline=8,
        splines=(WorldSpline(1, True, knots, knots),),
        scene_units={"one_meter_system_units": 100.0, "display_unit": "meters", "system_type": "centimeters"},
    )


def _annotation() -> WallEdgeAnnotation:
    return WallEdgeAnnotation("Line001", 1, 4, (1,), (2, 3, 4))


def test_plan_uses_artist_wall_and_defaults_rest_to_walkway():
    plan = build_wall_edge_zone_plan(_geometry(), _annotation(), wall_band_meters=1.2, walkway_band_meters=0.6)
    assert plan["roles"]["wall_segments"] == [1]
    assert plan["roles"]["walkway_open_segments"] == [2, 3, 4]
    assert plan["zones"]["wall_band"]["distance_system_units"] == 120.0
    assert plan["zones"]["walkway_band"]["distance_system_units"] == 60.0
    assert plan["distribution_map_used"] is False
    assert plan["reference_image_coordinates_used"] is False
    assert plan["forest_pack_mutated"] is False


def test_segment_inward_normal_points_inside_for_ccw_boundary():
    plan = build_wall_edge_zone_plan(_geometry(), _annotation(), wall_band_meters=1.0, walkway_band_meters=0.5)
    wall = next(item for item in plan["segments"] if item["segment_index"] == 1)
    assert wall["role"] == "wall_edge"
    assert wall["inward_normal_world_xy"] == {"x": -0.0, "y": 1.0}


def test_point_classification_prioritizes_artist_wall_band():
    plan = build_wall_edge_zone_plan(_geometry(), _annotation(), wall_band_meters=1.0, walkway_band_meters=0.5)
    polygon = tuple(Point2(**item) for item in plan["boundary_polygon_world_xy"])
    segments = tuple(
        Segment2(
            segment_index=item["segment_index"],
            role=item["role"],
            start=Point2(**item["start_world_xy"]),
            end=Point2(**item["end_world_xy"]),
            inward_normal=Point2(**item["inward_normal_world_xy"]),
            length_system_units=item["length_system_units"],
        )
        for item in plan["segments"]
    )
    assert classify_point(Point2(500.0, 40.0), polygon=polygon, segments=segments, wall_band_system_units=100.0, walkway_band_system_units=50.0) == "wall_band"
    assert classify_point(Point2(500.0, 250.0), polygon=polygon, segments=segments, wall_band_system_units=100.0, walkway_band_system_units=50.0) == "interior"
    assert classify_point(Point2(500.0, 470.0), polygon=polygon, segments=segments, wall_band_system_units=100.0, walkway_band_system_units=50.0) == "walkway_band"
