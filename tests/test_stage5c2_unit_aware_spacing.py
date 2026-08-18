from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "density_stage5c2.py"

def spacing_block():
    s = BRIDGE.read_text(encoding="utf-8")
    start = s.index("fn configurePhysicalSpacingJson spacingMeters =")
    end = s.index("\n    ),", start)
    return s[start:end]

def test_spacing_uses_numeric_meter_conversion():
    block = spacing_block()
    assert 'local oneMeterSystemUnits = units.decodeValue "1m"' in block
    assert "local spacingSystemUnits = oneMeterSystemUnits * spacingMeters" in block
    assert "spacingText" not in block

def test_physical_spacing_command_exists():
    s = BRIDGE.read_text(encoding="utf-8")
    assert 'SET_PHYSICAL_SPACING|*' in s
    assert 'configurePhysicalSpacingJson spacingMeters' in s

def test_no_hardcoded_45000_in_spacing_function():
    assert "45000" not in spacing_block()

def test_app_default_is_075_meters():
    s = APP.read_text(encoding="utf-8")
    assert 'default=0.75' in s
    assert 'SET_PHYSICAL_SPACING|' in s

def test_bridge_version_matches_current_contract():
    s = BRIDGE.read_text(encoding="utf-8")
    assert "bridge_version" in s and "0.9.79" in s
