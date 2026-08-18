from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
RUNTIME = ROOT / "src" / "forest_manager" / "forest_control" / "scene_runtime.py"


def test_ui_scene_generation_uses_verified_manifest_runtime_facade():
    controller = CONTROLLER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")

    assert "from forest_manager.forest_control.scene_runtime import ForestSceneRuntime" in controller
    assert "execute_plant_group_manifest" not in controller
    assert "self.scene_runtime = scene_runtime or ForestSceneRuntime(service=self.service)" in controller
    assert "self.scene_runtime.execute_manifest(manifest)" in controller
    assert "self.scene_runtime.execute_manifest(manifest, strict_acceptance=False)" in controller

    assert "class ForestSceneRuntime:" in runtime
    assert "def execute_manifest(" in runtime
    assert "execute_plant_group_manifest(" in runtime


def test_unverified_stage8_plan_executor_is_not_part_of_official_runtime():
    runtime = RUNTIME.read_text(encoding="utf-8")

    assert "stage8_scene_execution" not in runtime
    assert "Stage8PlantingPlanSceneExecutor" not in runtime
    assert "prepare_plan" not in runtime
    assert "def execute_plan(" not in runtime
    assert "pre_scene_readiness" not in runtime
    assert "resolution_pipeline_gate" not in runtime
    assert "scene_execution_recovery" not in runtime
