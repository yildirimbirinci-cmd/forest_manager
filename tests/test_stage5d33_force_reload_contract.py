from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")

def test_bridge_identity_forces_reload():
    assert '\\\"bridge_version\\\":\\\"0.9.53\\\"' in BRIDGE
    assert '\\\"bridge_build_id\\\":\\\"stage5d33-json-endpoint-reload-20260816b\\\"' in BRIDGE
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in RUNTIME
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage5d33-json-endpoint-reload-20260816b"' in RUNTIME

def test_endpoint_is_not_double_escaped():
    start = BRIDGE.index('if command == "FOREST_CONTROL_DISCOVER" then')
    end = BRIDGE.index('if command == "GET_SCENE_UNITS" then', start)
    block = BRIDGE[start:end]
    assert 'return "{\\\"ok\\\":true,\\\"command\\\":\\\"FOREST_CONTROL_DISCOVER\\\"' in block
    assert 'return "{\\\\\\\"ok' not in block
