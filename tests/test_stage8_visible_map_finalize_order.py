from __future__ import annotations

import inspect

import forest_manager.forest_control.plant_group_execution as module


def test_visible_execution_finalizes_only_before_map_binding():
    source = inspect.getsource(module.execute_plant_group_manifest)
    finalize_call = "finalize = finalize_plant_group_areas("
    bind_call = "map_binding = bind_single_forest_diversity_map("

    assert source.count(finalize_call) == 1
    assert source.index(finalize_call) < source.index(bind_call)


def test_no_post_bind_finalize_can_reset_diversity_mode():
    source = inspect.getsource(module.execute_plant_group_manifest)
    bind_pos = source.index("map_binding = bind_single_forest_diversity_map(")
    tail = source[bind_pos:]

    assert "finalize_plant_group_areas(" not in tail
    assert "Scene-space diversity map binding did not verify" in tail
