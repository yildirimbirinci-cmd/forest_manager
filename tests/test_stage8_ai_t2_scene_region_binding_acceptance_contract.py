from __future__ import annotations

import inspect
import forest_manager.devtools.acceptance.stage8_ai_t2_scene_region_binding_acceptance as module


def test_acceptance_does_not_hardcode_ref02_semantic_roles():
    source = inspect.getsource(module)
    assert "expected_ref02_semantic_roles_bound" not in source
    assert "foreground_mass" not in source
    assert "mid_accent" not in source
    assert "purple_accent" not in source
    assert "structural_shrub" not in source


def test_acceptance_requires_exact_runtime_group_binding_coverage():
    source = inspect.getsource(module)
    assert "runtime_group_ids == bound_group_ids" in source
    assert 'binding["all_resolved_groups_bound"] is True' in source
    assert 'binding["resolved_group_count"] == binding["bound_group_count"]' in source
