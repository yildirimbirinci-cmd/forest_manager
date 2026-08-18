from pathlib import Path


def test_bridge_segment_selection_is_boolean_safe_and_identity_is_084():
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert r'\"bridge_version\":\"0.9.84\"' in bridge
    assert 'stage8-wall-edge-segment-bool-fix-20260818a' in bridge
    assert 'isSelectedSegment = (selectedBits[segmentIndex] == true)' in bridge
    assert 'if selectedBits[segmentIndex] then' not in bridge
    assert not bridge.startswith("\ufeff")


def test_runtime_bridge_points_to_084_staged_source():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/forest_manager/max_bridge/runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.84"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-wall-edge-segment-bool-fix-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_84.ms"' in text
