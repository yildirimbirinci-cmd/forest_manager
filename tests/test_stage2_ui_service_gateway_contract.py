from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
SERVICE = ROOT / "src" / "forest_manager" / "forest_control" / "service.py"


def test_ui_controller_routes_runtime_bridge_operations_through_service():
    controller = CONTROLLER.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert "from forest_manager.max_bridge.runtime_bridge import" not in controller
    assert "self.service.read_plant_group_manifest(" in controller
    assert "self.service.write_plant_group_manifest(" in controller
    assert "self.service.single_forest_area_bounds(" in controller
    assert "self.service.apply_plant_group_species_runtime(" in controller

    assert "def read_plant_group_manifest(" in service
    assert "def write_plant_group_manifest(" in service
    assert "def single_forest_area_bounds(" in service
    assert "def apply_plant_group_species_runtime(" in service
