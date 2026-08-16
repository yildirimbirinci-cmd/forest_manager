from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "src" / "forest_manager" / "forest_control" / "service.py").read_text(encoding="utf-8")


def test_read_only_discovery_endpoint():
    assert "fn getForestControlDiscoveryJson" in BRIDGE
    assert 'command == "FOREST_CONTROL_DISCOVER"' in BRIDGE
    assert "getPropNames forestNode" in BRIDGE
    assert "forestControlArrayMetadataJson" in BRIDGE


def test_python_facade_preserves_discovery_and_promoted_write_endpoints():
    # Stage 5D.32 discovery remains read-only, while later verified stages add
    # specialized transactional write endpoints to the same facade.
    assert 'send_command("FOREST_CONTROL_DISCOVER")' in SERVICE
    assert '"FOREST_CONTROL_SET_SCALAR"' in SERVICE
    assert '"FOREST_CONTROL_SET_COLOR"' in SERVICE
    assert '"FOREST_CONTROL_SET_ARRAY_SCALAR"' in SERVICE
    assert '"FOREST_CONTROL_SET_ARRAY_POINT3"' in SERVICE
    assert '"FOREST_CONTROL_SET_ARRAY_NODE_REF"' in SERVICE
    assert '"FOREST_CONTROL_SET_ARRAY_MATERIAL_REF"' in SERVICE
    assert '"FOREST_CONTROL_SET_ARRAY_CPROXY_REF"' in SERVICE


def test_bridge_identity_matches_runtime():
    assert "0.9.54" in BRIDGE
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in RUNTIME
    assert "stage8-13-atomic-source-area-contract-20260816a" in BRIDGE
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-13-atomic-source-area-contract-20260816a"' in RUNTIME


def test_stage5d32_discovery_json_is_not_double_escaped():
    block = BRIDGE[BRIDGE.index("fn getForestControlDiscoveryJson"):BRIDGE.index("fn handleCommand rawCommand")]
    assert "{\\\\\"read_only" not in block
    assert "{\\\"read_only" in block


def test_stage5d32_time_values_remain_read_only():
    block = BRIDGE[BRIDGE.index("fn forestControlWriteMode"):BRIDGE.index("fn forestControlArrayMetadataJson")]
    assert 'valueClass == "Time"' not in block
