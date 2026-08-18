from pathlib import Path


def test_bridge_helper_layer_contract():
    text = (Path(__file__).resolve().parents[1] / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert r'\"bridge_version\":\"0.9.99\"' in text
    assert r'\"bridge_build_id\":\"stage8-helper-layer-lifecycle-20260818a\"' in text
    assert 'LayerManager.getLayerFromName "FM_HELPERS"' in text
    assert 'LayerManager.newLayerFromName "FM_HELPERS"' in text
    assert 'helperLayer.addNode node' in text
    assert 'helperLayer.addNode helper' in text
    assert 'helperLayer.on = false' in text
    assert 'FM_STAGE8_ENSURE_HELPER_LAYER' in text


def test_sync_calls_helper_layer_before_helper_listing():
    text = (Path(__file__).resolve().parents[1] / "src" / "forest_manager" / "forest_control" / "vector_region_helpers.py").read_text(encoding="utf-8")
    assert 'layer = ensure_stage8_helper_layer(preflight=preflight)' in text
    assert 'before = list_stage8_vector_region_helpers(source, preflight=False)' in text
    assert '"helper_layer": layer' in text


def test_runtime_bridge_identity_and_layer_endpoint():
    text = (Path(__file__).resolve().parents[1] / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.99"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_99.ms"' in text
    assert 'def ensure_stage8_helper_layer' in text
