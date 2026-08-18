from __future__ import annotations

import inspect

import forest_manager.forest_control.scene_space_semantic_regions as module


def test_contract_uses_world_space_spline_reader():
    source = inspect.getsource(module)
    assert "read_selected_spline_world_space" in source
    assert "selected_3ds_max_spline_world_samples" in source


def test_contract_does_not_project_reference_image_coordinates():
    source = inspect.getsource(module)
    assert '"reference_image_coordinates_used": False' in source
    assert "reference_image_role" in source
    assert "pixel_to_scene" not in source
    assert "image_mask_projection" not in source


def test_contract_does_not_mutate_forest_pack():
    source = inspect.getsource(module)
    assert '"forest_pack_mutated": False' in source
    assert "send_command(" not in source


def test_fallback_orientation_is_never_claimed_as_confirmed_frontage():
    source = inspect.getsource(module.build_semantic_region_plan)
    assert '"deterministic_minor_geometry_axis"' in source
    assert "site_front_confirmed = False" in source
