from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "live_source_area_contract_stage5d14_1.py"


def probe_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getLiveSourceAreaContractJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_probe_is_selection_independent_and_read_only():
    block = probe_block()
    assert 'getNodeByName "FM_Forest_001"' in block
    assert "getSingleSelection" not in block
    assert "setProperty" not in block
    assert '\\"read_only\\":true' in block


def test_probe_detects_direct_and_array_node_properties():
    block = probe_block()
    assert "isValidNode value" in block
    assert "isValidNode value[i]" in block
    assert "nodeArrayProps" in block
    assert "directNodeProps" in block


def test_probe_scans_area_source_and_geometry_keywords():
    block = probe_block()
    for term in ("area", "spline", "arn", "node", "source", "object", "geom"):
        assert f'findString lowerName "{term}"' in block


def test_probe_reports_managed_reference_layer_nodes():
    block = probe_block()
    assert 'LayerManager.getLayerFromName "FM_References"' in block
    assert 'getUserProp n "ForestManagerOwned"' in block
    assert '\\\"managed_reference_nodes\\\"' in block


def test_cli_calls_contract_probe():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_LIVE_SOURCE_AREA_CONTRACT")' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.53"' in bridge or '\\"bridge_version\\":\\"0.9.53\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in runtime
