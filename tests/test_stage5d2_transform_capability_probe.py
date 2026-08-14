from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "transform_probe_stage5d2.py"


def test_bridge_exposes_read_only_transform_probe():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_TRANSFORM_CAPABILITIES"' in source
    assert "getTransformCapabilityProbeJson()" in source
    assert '\\"read_only\\\":true' in source


def test_probe_discovers_actual_runtime_properties_instead_of_guessing():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "local props = getPropNames forestNode" in source
    assert 'findString propText "scale"' in source
    assert 'findString propText "rot"' in source
    assert 'findString propText "trans"' in source
    assert "getProperty forestNode propName" in source


def test_probe_reports_existing_geometry_scale_list_without_modifying_it():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "isProperty forestNode #ScaleList" in source
    assert "forestNode.ScaleList[i]" in source
    probe_start = source.index("fn getTransformCapabilityProbeJson")
    probe_end = source.index("fn getCompositionContextJson", probe_start)
    block = source[probe_start:probe_end]
    assert "forestNode.ScaleList[i] =" not in block


def test_cli_uses_auto_preflight_and_read_only_command():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_TRANSFORM_CAPABILITIES")' in source


def test_bridge_version_and_preflight_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '0.9.19' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.19"' in runtime


def test_density_command_is_not_changed_by_probe_stage():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "configureDensityMetersJson densityMeters" in source
