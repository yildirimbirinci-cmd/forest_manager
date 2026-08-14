from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
APP = ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py"


def test_native_density_command_exists():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "SET_NATIVE_DENSITY" in s
    assert "configureNativeDensityJson densityUnits" in s


def test_native_density_writes_units_without_meter_conversion():
    s = BRIDGE.read_text(encoding="utf-8")
    start = s.index("fn configureNativeDensityJson")
    end = s.index("fn configurePhysicalSpacingJson", start)
    block = s[start:end]
    assert "forestNode.units_x = densityUnits" in block
    assert "forestNode.units_y = densityUnits" in block
    assert "units.decodeValue" not in block


def test_generated_count_probe_is_non_authoritative():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "generated_count_authoritative" in s
    assert "generated_count_probe" in s
    assert "trees.count" in s


def test_cli_defaults_to_observed_75_density_units():
    s = APP.read_text(encoding="utf-8")
    assert "default=75.0" in s
    assert "SET_NATIVE_DENSITY" in s


def test_bridge_version_is_0_9_7():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "bridge_version" in s
    assert "0.9.7" in s
