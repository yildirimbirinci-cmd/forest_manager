from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")

def _endpoint_block() -> str:
    start = BRIDGE.index('if command == "FOREST_CONTROL_DISCOVER" then')
    end = BRIDGE.index('if command == "GET_SCENE_UNITS" then', start)
    return BRIDGE[start:end]

def test_forest_control_discover_returns_normal_json_not_double_escaped():
    block = _endpoint_block()
    assert 'return "{\\\"ok\\\":true,\\\"command\\\":\\\"FOREST_CONTROL_DISCOVER\\\",\\\"data\\\":"' in block
    assert 'return "{\\\\\\\"ok' not in block
