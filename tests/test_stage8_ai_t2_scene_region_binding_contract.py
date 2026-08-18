from __future__ import annotations

import inspect

import forest_manager.forest_control.ai_t2_scene_region_runtime as runtime


def test_runtime_invokes_existing_ai_t2_acceptance_not_scene_execution():
    source = inspect.getsource(runtime.run_ai_t2_resolution_acceptance)
    assert "stage8_ai_t2_resolution_acceptance" in source
    assert "stage8_ai_scene_execution_acceptance" not in source
    assert "stage8_scene_execution" not in source


def test_runtime_has_no_groups_json_argument_or_temp_file_contract():
    source = inspect.getsource(runtime)
    assert "--groups-json" not in source
    assert "NamedTemporaryFile" not in source
    assert "mkstemp" not in source


def test_runtime_manifest_fallback_is_read_only():
    source = inspect.getsource(runtime)
    assert "read_plant_group_manifest" in source
    assert "write_plant_group_manifest" not in source
    assert "execute_manifest" not in source


def test_runtime_requires_ai_t2_success_before_group_binding():
    source = inspect.getsource(runtime.run_ai_t2_resolution_acceptance)
    assert 'payload.get("ok") is not True' in source
    assert "completed.returncode != 0" in source
