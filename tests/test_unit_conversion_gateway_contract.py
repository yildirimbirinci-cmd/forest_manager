from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"
SEMANTIC = ROOT / "src" / "forest_manager" / "ui" / "semantic_calibration.py"
GATEWAY = ROOT / "src" / "forest_manager" / "forest_control" / "unit_conversion.py"


def test_ui_distance_conversion_routes_through_unit_gateway():
    controller = CONTROLLER.read_text(encoding="utf-8")
    semantic = SEMANTIC.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")

    assert "UnitConversionGateway.display_contract(scene_units)" in controller
    assert "UnitConversionGateway.system_to_display(value, scene_units)" in controller
    assert "UnitConversionGateway.display_to_system(value, scene_units)" in controller

    assert 'self.controller._display_distance_to_system(profile["size_m"]' not in semantic
    assert 'UnitConversionGateway.display_to_system(profile["size_m"]' in semantic

    assert "class UnitConversionGateway:" in gateway
    assert "def system_to_display(" in gateway
    assert "def display_to_system(" in gateway
