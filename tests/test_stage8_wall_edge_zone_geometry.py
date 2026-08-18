from __future__ import annotations

from forest_manager.forest_control.wall_edge_zone_geometry import (
    WallEdgeZoneGeometryError,
    build_wall_edge_zone_geometry,
)


def _plan():
    return {
        "verified": True,
        "node_name": "Line001",
        "spline_index": 1,
        "scene_units": {"one_meter_system_units": 100.0},
        "boundary_polygon_world_xy": [
            {"x": 0.0, "y": 0.0},
            {"x": 1000.0, "y": 0.0},
            {"x": 1000.0, "y": 500.0},
            {"x": 0.0, "y": 500.0},
        ],
        "segments": [
            {"segment_index": 1, "role": "wall_edge", "start_world_xy": {"x": 0.0, "y": 0.0}, "end_world_xy": {"x": 1000.0, "y": 0.0}, "inward_normal_world_xy": {"x": 0.0, "y": 1.0}},
            {"segment_index": 2, "role": "walkway_open_edge", "start_world_xy": {"x": 1000.0, "y": 0.0}, "end_world_xy": {"x": 1000.0, "y": 500.0}, "inward_normal_world_xy": {"x": -1.0, "y": 0.0}},
            {"segment_index": 3, "role": "walkway_open_edge", "start_world_xy": {"x": 1000.0, "y": 500.0}, "end_world_xy": {"x": 0.0, "y": 500.0}, "inward_normal_world_xy": {"x": 0.0, "y": -1.0}},
            {"segment_index": 4, "role": "walkway_open_edge", "start_world_xy": {"x": 0.0, "y": 500.0}, "end_world_xy": {"x": 0.0, "y": 0.0}, "inward_normal_world_xy": {"x": 1.0, "y": 0.0}},
        ],
        "zones": {
            "wall_band": {"distance_system_units": 120.0},
            "walkway_band": {"distance_system_units": 60.0},
        },
    }


def test_materializes_wall_walkway_and_interior_vector_polygons():
    result = build_wall_edge_zone_geometry(_plan())
    assert result["verified"] is True
    assert len(result["wall_band"]["parts"]) == 1
    assert len(result["walkway_band"]["parts"]) == 3
    assert len(result["interior"]["parts"]) == 1
    assert result["distribution_map_used"] is False
    assert result["forest_pack_mutated"] is False


def test_wall_priority_removes_wall_strip_from_walkway_parts():
    result = build_wall_edge_zone_geometry(_plan())
    for part in result["walkway_band"]["parts"]:
        assert all(point["y"] >= 120.0 - 1e-6 for point in part["points_world_xy"])


def test_interior_is_offset_from_all_boundary_roles():
    result = build_wall_edge_zone_geometry(_plan())
    points = result["interior"]["parts"][0]["points_world_xy"]
    assert {round(point["x"], 6) for point in points} == {60.0, 940.0}
    assert {round(point["y"], 6) for point in points} == {120.0, 440.0}


def test_non_convex_boundary_fails_closed():
    plan = _plan()
    plan["boundary_polygon_world_xy"] = [
        {"x": 0.0, "y": 0.0},
        {"x": 1000.0, "y": 0.0},
        {"x": 400.0, "y": 200.0},
        {"x": 1000.0, "y": 500.0},
        {"x": 0.0, "y": 500.0},
    ]
    try:
        build_wall_edge_zone_geometry(plan)
    except WallEdgeZoneGeometryError as exc:
        assert "convex" in str(exc).lower()
    else:
        raise AssertionError("Expected non-convex boundary to fail closed.")
