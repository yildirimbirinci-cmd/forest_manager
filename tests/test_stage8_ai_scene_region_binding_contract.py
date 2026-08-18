from __future__ import annotations

import inspect

import forest_manager.forest_control.ai_scene_region_binding as module


def test_role_map_is_explicit_and_small():
    assert module.ROLE_TO_REGION == {
        "foreground_mass": "foreground",
        "mid_accent": "midground",
        "purple_accent": "midground",
        "flower_accent": "midground",
        "structural_shrub": "background",
    }


def test_contract_has_no_forest_pack_mutation():
    source = inspect.getsource(module)
    assert "send_command(" not in source
    assert '"forest_pack_mutated": False' in source


def test_contract_excludes_unresolved_groups():
    source = inspect.getsource(module.extract_resolved_groups)
    assert "if not names:" in source
    assert "continue" in source


def test_contract_does_not_use_reference_image_coordinates():
    source = inspect.getsource(module)
    assert '"reference_image_coordinates_used": False' in source
    assert "pixel_to_scene" not in source
    assert "image_mask_projection" not in source
