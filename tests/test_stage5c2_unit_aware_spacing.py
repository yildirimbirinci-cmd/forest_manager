from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
APP = ROOT / "src" / "forest_manager" / "app" / "density_stage5c2.py"


def test_spacing_uses_max_unit_decoder():
    s = BRIDGE.read_text(encoding="utf-8")
    assert 'units.decodeValue "1m"' in s
    assert 'units.decodeValue spacingText' in s


def test_physical_spacing_command_exists():
    s = BRIDGE.read_text(encoding="utf-8")
    assert 'SET_PHYSICAL_SPACING|*' in s
    assert 'configurePhysicalSpacingJson spacingMeters' in s


def test_no_hardcoded_45000_in_new_spacing_function():
    s = BRIDGE.read_text(encoding="utf-8")
    start = s.index("fn configurePhysicalSpacingJson")
    end = s.index("fn getOrCreateReferenceLayer", start)
    block = s[start:end]
    assert "45000" not in block


def test_app_default_is_075_meters():
    s = APP.read_text(encoding="utf-8")
    assert 'default=0.75' in s
    assert 'SET_PHYSICAL_SPACING|' in s


def test_bridge_version_095():
    s = BRIDGE.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.5\\"' in s
