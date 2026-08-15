from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "prepare_species_layers_stage5d15.py"


def split_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn prepareSpeciesLayerForestsJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_split_uses_authoritative_live_contracts():
    block = split_block()
    assert "sourceForest.cobjlist" in block
    assert "findForestAreaSpline sourceForest" in block
    assert "tempnamelist" not in block
    assert "sourceForest.arnodes" not in block


def test_split_is_transactional_and_preserves_source_forest():
    block = split_block()
    assert "local created = #()" in block
    assert "for node in created do" in block
    assert "delete node" in block
    assert "delete sourceForest" not in block
    assert '\\"source_forest_preserved\\":true' in block


def test_existing_layer_cleanup_is_ownership_guarded():
    block = split_block()
    assert "isForestManagerOwnedNode existing" in block
    assert "Refusing to replace non-owned Forest layer" in block
    assert "delete existing" in block


def test_new_layers_reuse_existing_sources_and_same_spline():
    block = split_block()
    assert "local sourceNode = sourceForest.cobjlist[i]" in block
    assert "bindForestGeometrySource layerForest sourceNode" in block
    assert "addSplineIncludeArea layerForest splineNode" in block


def test_prepared_layers_are_disabled_to_avoid_double_scatter():
    block = split_block()
    assert "layerForest.disabled = true" in block
    assert "prepared_layers_disabled" in block


def test_common_density_cluster_and_transform_state_are_copied():
    block = split_block()
    for token in (
        "layerForest.units_x = oldDensityX",
        "layerForest.units_y = oldDensityY",
        "layerForest.divers = oldDivers",
        "layerForest.clusize = oldClusize",
        "layerForest.clurough = oldClurough",
        "layerForest.cluedge = oldCluedge",
        "layerForest.clunoise = oldClunoise",
        "layerForest.applyscale = oldApplyScale",
        "layerForest.applyrotation = oldApplyRotation",
        "layerForest.applytranslation = oldApplyTranslation",
    ):
        assert token in block


def test_cli_requires_three_disabled_verified_layers():
    source = APP.read_text(encoding="utf-8")
    assert 'send_command("PREPARE_SPECIES_LAYER_FORESTS")' in source
    assert "if len(layers) != 3" in source
    assert "if not layer.get(\"disabled\")" in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.31"' in bridge or '\\"bridge_version\\":\\"0.9.31\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.31"' in runtime
