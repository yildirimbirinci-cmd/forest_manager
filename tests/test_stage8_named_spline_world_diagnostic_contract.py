from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")

def test_named_spline_world_diagnostic_contract():
    assert 'FM_STAGE8_GET_NAMED_SPLINE_WORLD_SPACE' in BRIDGE
    assert 'getNamedSplineWorldSpaceJson' in BRIDGE
    assert 'nodeGetBoundingBox node node.transform' in BRIDGE
    assert 'get_named_spline_world_space' in RUNTIME
    assert '0.9.103' in BRIDGE
    assert '0.9.103' in RUNTIME
