from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BRIDGE=(ROOT/"maxscripts"/"ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME=(ROOT/"src"/"forest_manager"/"max_bridge"/"runtime_bridge.py").read_text(encoding="utf-8")
SERVICE=(ROOT/"src"/"forest_manager"/"forest_control"/"service.py").read_text(encoding="utf-8")
def test_read_only_discovery_endpoint():
    assert "fn getForestControlDiscoveryJson" in BRIDGE and 'command == "FOREST_CONTROL_DISCOVER"' in BRIDGE
    assert "getPropNames forestNode" in BRIDGE and "forestControlArrayMetadataJson" in BRIDGE
def test_python_facade_is_read_only():
    assert 'send_command("FOREST_CONTROL_DISCOVER")' in SERVICE and "FOREST_CONTROL_SET" not in SERVICE
def test_bridge_identity_matches_runtime():
    assert "0.9.53" in BRIDGE and 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in RUNTIME
    assert "stage5d33-json-endpoint-reload-20260816b" in BRIDGE and 'EXPECTED_BRIDGE_BUILD_ID = "stage5d33-json-endpoint-reload-20260816b"' in RUNTIME

def test_stage5d32_discovery_json_is_not_double_escaped():
    block = BRIDGE[BRIDGE.index("fn getForestControlDiscoveryJson"):BRIDGE.index("fn handleCommand rawCommand")]
    assert "{\\\\\"read_only" not in block
    assert "{\\\"read_only" in block


def test_stage5d32_time_values_remain_read_only():
    block = BRIDGE[BRIDGE.index("fn forestControlWriteMode"):BRIDGE.index("fn forestControlArrayMetadataJson")]
    assert 'valueClass == "Time"' not in block

