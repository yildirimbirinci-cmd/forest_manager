from __future__ import annotations

from forest_manager.forest_control.scene_space_distribution import (
    SceneBoundaryRuntime,
    build_scene_space_boundary_foundation,
)


class FakeBoundaryRuntime(SceneBoundaryRuntime):
    def read_selected_boundary(self, *, preflight: bool = True):
        from forest_manager.forest_control.scene_space_distribution import (
            SceneBoundarySnapshot,
            SceneUnitSnapshot,
        )

        return SceneBoundarySnapshot(
            node_name="Line001",
            node_class="line",
            spline_count=1,
            all_splines_closed=True,
            width_system_units=10121.5,
            depth_system_units=10420.9,
            height_system_units=0.0,
            units=SceneUnitSnapshot(
                display_type="metric",
                display_unit="meters",
                system_type="centimeters",
                system_scale=1.0,
                one_meter_system_units=100.0,
                one_centimeter_system_units=1.0,
                one_millimeter_system_units=0.1,
            ),
        )


def test_boundary_foundation_uses_scene_geometry_and_units():
    result = build_scene_space_boundary_foundation(runtime=FakeBoundaryRuntime())
    boundary = result["boundary"]

    assert result["verified"] is True
    assert boundary["node_name"] == "Line001"
    assert boundary["all_splines_closed"] is True
    assert round(boundary["width_meters"], 3) == 101.215
    assert round(boundary["depth_meters"], 3) == 104.209
    assert boundary["coordinate_source"] == "selected_3ds_max_boundary"


def test_reference_image_projection_is_explicitly_forbidden():
    result = build_scene_space_boundary_foundation(runtime=FakeBoundaryRuntime())
    boundary = result["boundary"]

    assert result["distribution_policy"] == "scene_geometry_only"
    assert result["reference_image_role"] == "semantic_design_guidance_only"
    assert result["map_policy"] == "parked_not_projected_from_reference_image"
    assert boundary["reference_image_projection"] is False


def test_exact_polygon_remap_waits_for_world_space_vertices():
    result = build_scene_space_boundary_foundation(runtime=FakeBoundaryRuntime())

    assert result["exact_polygon_remap_ready"] is False
    assert result["next_requirement"] == "bridge_world_space_spline_vertex_sampling"
    assert result["scene_mutated"] is False
