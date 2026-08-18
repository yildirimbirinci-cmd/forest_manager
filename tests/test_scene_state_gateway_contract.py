from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
GATEWAY = ROOT / "src" / "forest_manager" / "forest_control" / "scene_state.py"


def test_controller_uses_single_scene_state_gateway_for_manifest_io():
    controller = CONTROLLER.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")

    assert "from forest_manager.forest_control.scene_state import SceneStateGateway" in controller
    assert "self.scene_state = scene_state or SceneStateGateway(self.service)" in controller
    assert "self.service.read_plant_group_manifest" not in controller
    assert "self.service.write_plant_group_manifest" not in controller
    assert "class SceneStateGateway:" in gateway
    assert "self.service.read_plant_group_manifest" in gateway
    assert "self.service.write_plant_group_manifest" in gateway


def test_apply_uses_one_authoritative_snapshot_and_working_copy():
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "previous_manifest, manifest = self.scene_state.snapshot_and_working_copy(preflight=False)" in controller
    assert "self.scene_state.restore_snapshot(previous_manifest, preflight=False)" in controller
    assert "self.scene_state.write_verified(" in controller


def test_pending_edit_buffer_contract_remains_separate():
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "self._pending: dict[str, PendingEdit] = {}" in controller
    assert "pending_edits=tuple(self._pending.values())" in controller
    assert "def set_pending_value(" in controller
