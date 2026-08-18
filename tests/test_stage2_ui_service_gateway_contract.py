from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
SERVICE = ROOT / "src" / "forest_manager" / "forest_control" / "service.py"
SCENE_STATE = ROOT / "src" / "forest_manager" / "forest_control" / "scene_state.py"


def test_ui_controller_routes_runtime_bridge_operations_through_service():
    controller = CONTROLLER.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    scene_state = SCENE_STATE.read_text(encoding="utf-8")

    assert "from forest_manager.max_bridge.runtime_bridge import" not in controller

    # Authoritative manifest access is centralized one level above the service.
    assert "self.service.read_plant_group_manifest(" not in controller
    assert "self.service.write_plant_group_manifest(" not in controller
    assert "SceneStateGateway" in controller
    assert "self.scene_state" in controller
    assert "self.service.read_plant_group_manifest(" in scene_state
    assert "self.service.write_plant_group_manifest(" in scene_state

    # Other live Forest operations still route through the service gateway.
    assert "self.service.single_forest_area_bounds(" in controller
    assert "self.service.apply_plant_group_species_runtime(" in controller

    assert "def read_plant_group_manifest(" in service
    assert "def write_plant_group_manifest(" in service
    assert "def single_forest_area_bounds(" in service
    assert "def apply_plant_group_species_runtime(" in service
