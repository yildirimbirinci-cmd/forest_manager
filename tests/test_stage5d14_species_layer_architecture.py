from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "species_layer_architecture_stage5d14.py"


def context_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getSpeciesLayerContextJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_bridge_context_is_selection_independent_and_read_only():
    block = context_block()
    assert 'getNodeByName "FM_Forest_001"' in block
    assert "getSingleSelection" not in block
    assert "setProperty" not in block
    assert '\\"read_only\\":true' in block


def test_context_reports_live_geometry_sources_probabilities_and_areas():
    block = context_block()
    assert "forestNode.namelist" in block
    assert "forestNode.tempnamelist" in block
    assert "forestNode.problist" in block
    assert "forestNode.arnodes" in block


def test_context_density_and_cluster_size_are_unit_aware():
    block = context_block()
    assert 'units.decodeValue "1m"' in block
    assert "forestNode.units_x / oneMeter" in block
    assert "forestNode.clusize / oneMeter" in block


def test_architecture_is_preview_only():
    source = APP.read_text(encoding="utf-8")
    assert '"read_only": True' in source
    assert 'send_command("GET_SPECIES_LAYER_CONTEXT")' in source
    assert "APPLY_" not in source
    assert "SET_" not in source


def test_architecture_keeps_legacy_forest_for_rollback():
    source = APP.read_text(encoding="utf-8")
    assert "keep FM_Forest_001 unchanged as rollback source during migration" in source
    assert "never delete the user spline or unrelated scene objects" in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.39"' in bridge or '\\"bridge_version\\":\\"0.9.39\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.39"' in runtime
