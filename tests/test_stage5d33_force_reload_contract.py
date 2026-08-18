from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")


def test_bridge_identity_forces_reload():
    # The identity has advanced since Stage 5D.33; this regression contract must
    # verify the currently shipped bridge/runtime pair, not pin the historical id.
    assert '\\"bridge_version\\":\\"0.9.79\\"' in BRIDGE
    assert '\\"bridge_build_id\\":\\"stage8-world-map-projection-20260818q\\"' in BRIDGE
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in RUNTIME
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-world-map-projection-20260818q"' in RUNTIME


def test_endpoint_is_not_double_escaped():
    start = BRIDGE.index('if command == "FOREST_CONTROL_DISCOVER" then')
    end = BRIDGE.index('if command == "GET_SCENE_UNITS" then', start)
    block = BRIDGE[start:end]
    assert 'return "{\\\"ok\\\":true,\\\"command\\\":\\\"FOREST_CONTROL_DISCOVER\\\"' in block
    assert 'return "{\\\\\\\"ok' not in block
