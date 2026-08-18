from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLANT = ROOT / "src" / "forest_manager" / "forest_control" / "plant_group_execution.py"
ASSET = ROOT / "src" / "forest_manager" / "forest_control" / "stage8_asset_resolution.py"
SERVICE = ROOT / "src" / "forest_manager" / "forest_control" / "service.py"


def test_stage2_high_level_forest_control_does_not_bypass_service_gateway():
    plant = PLANT.read_text(encoding="utf-8")
    asset = ASSET.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert "send_command(" not in plant
    assert "send_command(" not in asset
    assert "def single_forest_area_polygon(" in service
    assert "def merge_t2_asset(" in service
    assert 'svc.set_property(\n        forest_name,\n        "distmap",\n        None,' in plant
    assert "service.set_array_element(" in plant
    assert "self.control_service.merge_t2_asset(" in asset
