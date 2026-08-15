from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "cluster_probe_stage5d7.py"


def test_bridge_exposes_read_only_cluster_probe():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_CLUSTER_CAPABILITIES"' in source
    assert "getClusterCapabilityProbeJson()" in source
    assert '\\"read_only\\":true' in source


def test_probe_targets_cluster_diversity_and_geometry_properties():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'findString lowerName "cluster"' in source
    assert 'findString lowerName "clump"' in source
    assert 'findString lowerName "divers"' in source
    assert 'findString lowerName "geom"' in source
    assert 'findString lowerName "prob"' in source


def test_probe_does_not_write_forest_properties():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getClusterCapabilityProbeJson")
    end = source.index("\n    ),", start)
    block = source[start:end]
    assert "setProperty" not in block
    assert "forestNode.distmode =" not in block
    assert "forestNode.units_x =" not in block
    assert "forestNode.units_y =" not in block


def test_cli_uses_automatic_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_CLUSTER_CAPABILITIES")' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.22"' in bridge or '\\"bridge_version\\":\\"0.9.22\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.22"' in runtime


def test_no_density_value_is_changed():
    source = APP.read_text(encoding="utf-8")
    assert "75.0" not in source
