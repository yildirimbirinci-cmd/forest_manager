from pathlib import Path


def test_maxscript_exposes_named_atomic_geometry_source_endpoints():
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_ADD_GEOMETRY_SOURCE" in bridge
    assert "FOREST_CONTROL_REMOVE_GEOMETRY_SOURCE_TAIL" in bridge
    assert "fn addNamedGeometrySourceJson" in bridge
    assert "fn removeGeometrySourceTailJson" in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
    assert 'stage8-world-map-projection-20260818q' in runtime
