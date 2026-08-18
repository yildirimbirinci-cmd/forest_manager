from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "density_stage5c3.py"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"

def density_block():
    s = BRIDGE.read_text(encoding="utf-8")
    start = s.index("fn configureDensityMetersJson densityMeters =")
    end = s.index("\n    ),", start)
    return s[start:end]

def test_density_command_uses_explicit_meter_contract():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "SET_DENSITY_METERS" in s
    assert "configureDensityMetersJson densityMeters" in s

def test_density_uses_shared_active_scene_unit_conversion():
    block = density_block()
    assert "local oneMeterSystemUnits = metersToSystemUnits 1.0" in block
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in block
    assert "forestNode.units_x = densitySystemUnits" in block
    assert "forestNode.units_y = densitySystemUnits" in block

def test_generated_count_probe_remains_non_authoritative():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "generated_count_authoritative" in s
    assert "generated_count_probe" in s
    assert "trees.count" in s

def test_cli_defaults_to_exact_75_meters():
    s = APP.read_text(encoding="utf-8")
    assert "default=75.0" in s
    assert "SET_DENSITY_METERS" in s

def test_bridge_and_runtime_use_same_current_version():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "0.9.79" in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
