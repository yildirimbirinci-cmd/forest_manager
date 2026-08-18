from __future__ import annotations

import inspect

import forest_manager.devtools.acceptance.stage8_visible_scene_space_execution_acceptance as module


def test_visible_acceptance_prepares_sources_before_scene_execution():
    source = inspect.getsource(module.main)
    assert "_prepare_geometry_sources(manifest, resolution, service=service)" in source
    assert source.index("_prepare_geometry_sources") < source.index("runtime.execute_manifest")


def test_source_preparation_reuses_scene_node_before_merge():
    source = inspect.getsource(module._prepare_geometry_sources)
    assert "service.add_geometry_source_by_name" in source
    assert "resolver.merge_resolved_asset" in source
    assert source.index("service.add_geometry_source_by_name") < source.index("resolver.merge_resolved_asset")


def test_source_preparation_rejects_missing_or_duplicate_sources():
    source = inspect.getsource(module._prepare_geometry_sources)
    assert "Required Geometry sources remain missing" in source
    assert "Duplicate Geometry sources detected after preparation" in source
