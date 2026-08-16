from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "density_stage5c2.py"


def test_spacing_uses_numeric_meter_conversion():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'local oneMeterSystemUnits = units.decodeValue "1m"' in source
    assert "local spacingSystemUnits = oneMeterSystemUnits * spacingMeters" in source
    assert "spacingText" not in source


def test_zero_spacing_cannot_verify():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "if spacingSystemUnits <= 0.0 do" in source
    assert "Forest units must be positive" in source


def test_cli_rejects_non_positive_returned_units():
    source = APP.read_text(encoding="utf-8")
    assert "spacing_system_units <= 0.0" in source
    assert "units_x <= 0.0" in source
    assert "units_y <= 0.0" in source


def test_bridge_version_is_0_9_6():
    source = BRIDGE.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.54\\"' in source
