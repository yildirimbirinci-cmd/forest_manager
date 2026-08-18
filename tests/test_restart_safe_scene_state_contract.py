from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
SCENE_STATE = ROOT / "src" / "forest_manager" / "forest_control" / "scene_state.py"


def test_restart_state_contract_is_scene_authoritative():
    controller = CONTROLLER.read_text(encoding="utf-8")
    scene_state = SCENE_STATE.read_text(encoding="utf-8")

    assert "self.scene_state.read_manifest(preflight=False)" in controller
    assert "discover_plant_groups(forests, group_manifest)" in controller
    assert "self._group_runtime_cache.clear()" in controller
    assert "self._pending.clear()" in controller
    assert "pending_edits=()" in controller

    assert "The 3ds Max manifest is authoritative" in scene_state
    assert "runtime caches are" in scene_state
    assert "non-authoritative projections" in scene_state


def test_restart_does_not_add_disk_persistence_for_ui_selection_or_pending_edits():
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "QSettings" not in controller
    assert "selected_group_id.json" not in controller
    assert "pending_edits.json" not in controller
