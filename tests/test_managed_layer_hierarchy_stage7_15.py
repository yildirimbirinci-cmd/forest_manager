from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")


def test_bridge_identity_matches_runtime():
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in RUNTIME
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-versioned-bridge-no-watcher-20260817a"' in RUNTIME
    assert r'\"bridge_version\":\"0.9.79\"' in BRIDGE
    assert r'\"bridge_build_id\":\"stage8-versioned-bridge-no-watcher-20260817a\"' in BRIDGE


def test_managed_child_layers_are_parented():
    assert 'getOrCreateManagedChildLayer "FM_FORESTS"' in BRIDGE
    assert 'getOrCreateManagedChildLayer "FM_REFERENCES"' in BRIDGE
    assert 'childLayer.setParent managedLayer' in BRIDGE


def test_reference_layer_is_hidden_frozen_and_locked():
    assert 'setLayerProtectionState referencesLayer true true false' in BRIDGE
    assert 'refLayer.on = false' in BRIDGE
    assert 'refLayer.isFrozen = true' in BRIDGE
    assert 'refLayer.lock = true' in BRIDGE


def test_forest_layer_is_visible_frozen_and_locked():
    assert 'setLayerProtectionState forestsLayer true true true' in BRIDGE


def test_legacy_reference_layer_is_migrated_safely():
    assert 'fn migrateLegacyReferenceLayer' in BRIDGE
    assert 'LayerManager.getLayerFromName "FM_References"' in BRIDGE
    assert 'isForestManagerOwnedNode node' in BRIDGE
    assert 'targetLayer.addNode node' in BRIDGE


def test_status_reports_child_layer_states():
    assert r'\"forests_layer\"' in BRIDGE
    assert r'\"references_layer\"' in BRIDGE
    assert r'\"managed_reference_count\"' in BRIDGE
