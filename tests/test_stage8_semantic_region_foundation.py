from __future__ import annotations

from forest_manager.forest_control.scene_space_semantic_regions import (
    Point2,
    build_semantic_region_plan,
    normalize_ccw,
    point_in_polygon,
    signed_area,
)
from forest_manager.forest_control.spline_world_space import (
    SelectedSplineWorldSpace,
    WorldPoint,
    WorldSpline,
)


def _geometry() -> SelectedSplineWorldSpace:
    samples = (
        WorldPoint(0.0, 0.0, 0.0),
        WorldPoint(2.5, 0.0, 0.0),
        WorldPoint(5.0, 0.0, 0.0),
        WorldPoint(10.0, 0.0, 0.0),
        WorldPoint(10.0, 2.5, 0.0),
        WorldPoint(10.0, 5.0, 0.0),
        WorldPoint(5.0, 5.0, 0.0),
        WorldPoint(0.0, 5.0, 0.0),
        WorldPoint(0.0, 2.5, 0.0),
    )
    return SelectedSplineWorldSpace(
        node_name="Line001",
        node_class="line",
        coordinate_system="world",
        spline_count=1,
        samples_per_spline=len(samples),
        splines=(
            WorldSpline(
                spline_index=1,
                closed=True,
                knots=(
                    WorldPoint(0.0, 0.0, 0.0),
                    WorldPoint(10.0, 0.0, 0.0),
                    WorldPoint(10.0, 5.0, 0.0),
                    WorldPoint(0.0, 5.0, 0.0),
                ),
                samples=samples,
            ),
        ),
        scene_units={"one_meter_system_units": 1.0},
    )


def test_polygon_is_normalized_ccw():
    polygon = normalize_ccw(
        [Point2(0, 0), Point2(0, 5), Point2(10, 5), Point2(10, 0)]
    )
    assert signed_area(polygon) > 0.0


def test_semantic_regions_use_real_scene_polygon_not_reference_pixels():
    result = build_semantic_region_plan(_geometry(), front_hint_world_xy=(0.0, -1.0))

    assert result["node_name"] == "Line001"
    assert result["site_polygon"]["source"] == "selected_3ds_max_spline_world_samples"
    assert result["reference_image_coordinates_used"] is False
    assert result["forest_pack_mutated"] is False
    assert [region["semantic_role"] for region in result["regions"]] == [
        "foreground",
        "midground",
        "background",
    ]


def test_explicit_front_hint_is_confirmed_and_depth_axis_points_back():
    result = build_semantic_region_plan(_geometry(), front_hint_world_xy=(0.0, -1.0))
    assert result["site_front_confirmed"] is True
    assert result["orientation_source"] == "explicit_front_hint"
    assert result["semantic_depth_axis_world_xy"] == {"x": -0.0, "y": 1.0}


def test_fallback_orientation_is_not_claimed_as_site_front():
    result = build_semantic_region_plan(_geometry())
    assert result["site_front_confirmed"] is False
    assert result["orientation_source"] == "deterministic_minor_geometry_axis"


def test_point_in_polygon_supports_site_constraint_checks():
    polygon = [Point2(0, 0), Point2(10, 0), Point2(10, 5), Point2(0, 5)]
    assert point_in_polygon(Point2(5, 2), polygon) is True
    assert point_in_polygon(Point2(15, 2), polygon) is False
