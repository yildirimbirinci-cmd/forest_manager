from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "distribution_probe_stage5d6.py"


def test_bridge_exposes_read_only_distribution_probe():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_DISTRIBUTION_CAPABILITIES"' in source
    assert "getDistributionCapabilityProbeJson()" in source
    assert '\\"read_only\\\":true' in source


def test_probe_searches_relevant_property_families():
    source = BRIDGE.read_text(encoding="utf-8")
    for token in ("dist", "map", "cluster", "group", "falloff", "edge"):
        assert f'findString propText "{token}"' in source


def test_probe_does_not_assign_distribution_properties():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getDistributionCapabilityProbeJson")
    end = source.index("\n    ),", start)
    block = source[start:end]
    assert "setProperty forestNode" not in block
    assert "forestNode.distmode =" not in block
    assert "forestNode.units_x =" not in block
    assert "forestNode.units_y =" not in block


def test_cli_uses_automatic_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_DISTRIBUTION_CAPABILITIES")' in source


def test_bridge_and_runtime_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '0.9.54' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in runtime


def test_density_is_only_reported_not_changed():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getDistributionCapabilityProbeJson")
    end = source.index("\n    ),", start)
    block = source[start:end]
    assert '\\"density_units_x\\\":' in block
    assert '\\"density_units_y\\\":' in block
