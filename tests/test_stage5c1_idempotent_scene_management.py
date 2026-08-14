from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"


def source():
    return BRIDGE.read_text(encoding="utf-8")


def test_nodes_get_explicit_forest_manager_ownership_marker():
    s = source()
    assert 'setUserProp node "ForestManagerOwned" "true"' in s
    assert 'setUserProp node "ForestManagerRole" role' in s


def test_reset_collects_sources_before_old_forest_delete():
    s = source()
    collect = s.index("oldManagedSources = collectManagedForestSourceNodes oldForest")
    delete = s.index("delete oldForest", collect)
    cleanup = s.index(
        "managedReferencesDeleted = deleteManagedReferenceNodes",
        delete,
    )
    assert collect < delete < cleanup


def test_cleanup_is_scoped_to_owned_or_legacy_forest_sources():
    s = source()
    assert "collectOwnedReferenceLayerNodes" in s
    assert "isForestManagerOwnedNode node" in s
    assert "legacySourceNodes" in s
    assert 'LayerManager.getLayerFromName "FM_References"' in s


def test_new_merge_nodes_are_marked_and_hidden_in_reference_layer():
    s = source()
    assert 'markForestManagerOwnedNode obj role:"merged_asset_node"' in s
    assert "refLayer.addNode obj" in s
    assert "refLayer.on = false" in s


def test_user_spline_is_not_deleted_by_reset_cleanup():
    s = source()
    reset_start = s.index("fn resetManagedForestFromSelectionJson")
    reset_end = s.index("fn stringEndsWith", reset_start)
    reset = s[reset_start:reset_end]
    assert "delete splineNode" not in reset
    assert "delete selection" not in reset


def test_reset_reports_deleted_managed_reference_count():
    s = source()
    assert '\\"managed_references_deleted\\":' in s


def test_bridge_version_is_0_9_4():
    s = source()
    assert '\\"bridge_version\\":\\"0.9.4\\"' in s
