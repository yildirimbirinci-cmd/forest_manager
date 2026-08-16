from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "density_stage5c3.py"
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"

def test_default_density_is_exactly_75_meters():
    s = APP.read_text(encoding="utf-8")
    assert 'parser.add_argument("--density-m", type=float, default=75.0)' in s

def test_bridge_converts_requested_meters_using_scene_units():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "local oneMeterSystemUnits = metersToSystemUnits 1.0" in s
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in s

def test_bridge_reports_requested_meter_value_and_internal_units():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "density_m" in s and "density_system_units" in s
    assert "units_x" in s and "units_y" in s

def test_bridge_version_matches_current_contract():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "bridge_version" in s and "0.9.54" in s
