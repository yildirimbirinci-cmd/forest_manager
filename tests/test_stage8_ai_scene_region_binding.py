from __future__ import annotations

from forest_manager.forest_control.ai_scene_region_binding import (
    AISceneRegionBindingError,
    build_ai_scene_region_binding_plan,
)


def _region_plan():
    return {
        "verified": True,
        "node_name": "Line001",
        "coordinate_system": "world",
        "orientation_source": "deterministic_minor_geometry_axis",
        "site_front_confirmed": False,
        "reference_image_coordinates_used": False,
        "forest_pack_mutated": False,
        "regions": [
            {
                "region_id": "scene_region:foreground",
                "semantic_role": "foreground",
                "constraint_type": "site_polygon_intersection_with_depth_projection_interval",
                "normalized_depth_interval": {"min": 0.0, "max": 0.32},
                "inside_site_polygon_required": True,
            },
            {
                "region_id": "scene_region:midground",
                "semantic_role": "midground",
                "constraint_type": "site_polygon_intersection_with_depth_projection_interval",
                "normalized_depth_interval": {"min": 0.32, "max": 0.68},
                "inside_site_polygon_required": True,
            },
            {
                "region_id": "scene_region:background",
                "semantic_role": "background",
                "constraint_type": "site_polygon_intersection_with_depth_projection_interval",
                "normalized_depth_interval": {"min": 0.68, "max": 1.0},
                "inside_site_polygon_required": True,
            },
        ],
    }


def _groups():
    return [
        {
            "group_id": "plant_group:1:foreground_mass",
            "semantic_role": "foreground_mass",
            "source_names": ["Lavandula angustifolia 'Hidcote' (Lavender)"],
        },
        {
            "group_id": "plant_group:2:mid_accent",
            "semantic_role": "mid_accent",
            "source_names": ["Rudbeckia 'Goldsturm' (Coneflower)"],
        },
        {
            "group_id": "plant_group:3:purple_accent",
            "semantic_role": "purple_accent",
            "source_names": ["Allium hollandicum 'Purple Sensation' (Ornamental onion)"],
        },
        {
            "group_id": "plant_group:4:flower_accent",
            "semantic_role": "flower_accent",
            "source_names": ["Allamanda"],
        },
        {
            "group_id": "plant_group:5:structural_shrub",
            "semantic_role": "structural_shrub",
            "source_names": ["Rosa canina (Dog rose)"],
        },
        {
            "group_id": "plant_group:6:unresolved",
            "semantic_role": "foreground_mass",
            "source_names": [],
        },
    ]


def test_resolved_groups_bind_to_expected_scene_regions():
    result = build_ai_scene_region_binding_plan(
        plant_groups=_groups(),
        scene_region_plan=_region_plan(),
    )
    mapping = {item["semantic_role"]: item["scene_region_role"] for item in result["bindings"]}
    assert mapping == {
        "foreground_mass": "foreground",
        "mid_accent": "midground",
        "purple_accent": "midground",
        "flower_accent": "midground",
        "structural_shrub": "background",
    }
    assert result["resolved_group_count"] == 5
    assert result["bound_group_count"] == 5


def test_unresolved_groups_are_excluded():
    result = build_ai_scene_region_binding_plan(
        plant_groups=_groups(),
        scene_region_plan=_region_plan(),
    )
    ids = {item["group_id"] for item in result["bindings"]}
    assert "plant_group:6:unresolved" not in ids
    assert result["unresolved_groups_excluded"] is True


def test_binding_is_deterministic():
    first = build_ai_scene_region_binding_plan(
        plant_groups=_groups(),
        scene_region_plan=_region_plan(),
    )
    second = build_ai_scene_region_binding_plan(
        plant_groups=_groups(),
        scene_region_plan=_region_plan(),
    )
    assert first["binding_plan_id"] == second["binding_plan_id"]
    assert first["bindings"] == second["bindings"]


def test_unknown_resolved_role_fails_closed():
    groups = [{"group_id": "x", "semantic_role": "unknown_role", "source_names": ["Plant"]}]
    try:
        build_ai_scene_region_binding_plan(
            plant_groups=groups,
            scene_region_plan=_region_plan(),
        )
    except AISceneRegionBindingError as exc:
        assert "No approved scene-region binding" in str(exc)
    else:
        raise AssertionError("Unknown resolved semantic roles must fail closed.")


def test_reference_image_coordinates_are_never_bound():
    result = build_ai_scene_region_binding_plan(
        plant_groups=_groups(),
        scene_region_plan=_region_plan(),
    )
    assert result["reference_image_coordinates_used"] is False
    assert all(
        item["reference_image_coordinates_used"] is False
        for item in result["bindings"]
    )
