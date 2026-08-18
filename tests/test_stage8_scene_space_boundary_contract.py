from __future__ import annotations

import inspect

import forest_manager.forest_control.scene_space_distribution as module


def test_runtime_uses_existing_read_only_measurement_command():
    source = inspect.getsource(module.SceneBoundaryRuntime.read_selected_boundary)
    assert 'send_command("GET_SELECTION_MEASUREMENTS")' in source
    assert "GET_SELECTION_SPLINE_VERTICES" not in source


def test_foundation_does_not_import_legacy_stage8_scene_executor():
    source = inspect.getsource(module)
    assert "stage8_scene_execution" not in source
    assert "Stage8PlantingPlanSceneExecutor" not in source


def test_contract_does_not_treat_bbox_as_distribution_geometry():
    source = inspect.getsource(module)
    assert '"exact_polygon_remap_ready": False' in source
    assert '"bridge_world_space_spline_vertex_sampling"' in source
    assert '"reference_image_projection": False' in source
