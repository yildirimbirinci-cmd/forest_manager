from pathlib import Path

def test_bridge_081_contract():
    root = Path(__file__).resolve().parents[1]
    text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8-sig")
    assert r'\"bridge_version\":\"0.9.81\"' in text
    assert r'\"bridge_build_id\":\"stage8-single-forest-area-polygon-20260818a\"' in text
    assert 'fn singleForestAreaPolygonJson forestName samples:256' in text
    assert 'pattern:"FM_SINGLE_FOREST_AREA_POLYGON|*|*"' in text
    assert 'in coordsys world' in text
    assert 'normalized_bbox_with_pil_y_flip' in text
    assert r'\"read_only\":true' in text

def test_runtime_bridge_targets_081():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.81"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-single-forest-area-polygon-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_81.ms"' in text
