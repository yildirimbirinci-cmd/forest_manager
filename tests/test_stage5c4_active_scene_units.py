from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
CLI = ROOT / "src" / "forest_manager" / "app" / "scene_units_stage5c4.py"


def source() -> str:
    return BRIDGE.read_text(encoding="utf-8")


def test_bridge_reads_active_display_and_system_units():
    s = source()
    assert "units.DisplayType" in s
    assert "units.MetricType" in s
    assert "units.USType" in s
    assert "units.SystemType" in s
    assert "units.SystemScale" in s


def test_bridge_exposes_scene_unit_contract():
    s = source()
    assert 'command == "GET_SCENE_UNITS"' in s
    assert '"GET_SCENE_UNITS"' in s
    assert "getSceneUnitsJson()" in s


def test_conversion_helpers_use_max_runtime_units():
    s = source()
    assert 'units.decodeValue "1m"' in s
    assert 'units.decodeValue "1mm"' in s
    assert "units.formatValue systemValue" in s


def test_density_uses_shared_runtime_conversion_and_reports_display_value():
    s = source()
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in s
    assert "local densityDisplayValue = formatSystemValueForScene densitySystemUnits" in s
    assert '\\"density_display_value\\"' in s
    assert '\\"display_unit\\"' in s
    assert '\\"system_type\\"' in s


def test_reference_offset_is_physical_and_scene_unit_aware():
    s = source()
    assert "local targetZ = millimetersToSystemUnits -1500.0" in s


def test_cli_requests_runtime_units():
    s = CLI.read_text(encoding="utf-8")
    assert 'send_command("GET_SCENE_UNITS")' in s
    assert "one_meter_system_units" in s


def test_bridge_version_is_0_9_12():
    s = source()
    assert "0.9.53" in s and "bridge_version" in s
