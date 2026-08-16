from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "species_mask_alignment_contract_stage5d21.py"


def probe_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getSpeciesMaskSpatialAlignmentContractJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_probe_is_read_only_and_keeps_layers_disabled():
    block = probe_block()
    assert "setProperty" not in block
    assert "forestNode.disabled =" not in block
    assert '\\"read_only\\":true' in block


def test_probe_reads_forest_and_bitmap_alignment_properties():
    block = probe_block()
    assert "getPropNames forestNode" in block
    assert "getPropNames mapNode" in block
    for term in ("offset", "scale", "tile", "align", "coord", "uvw"):
        assert f'findString lowerName "{term}"' in block


def test_probe_reports_spline_bounds():
    block = probe_block()
    assert "findForestAreaSpline sourceForest" in block
    assert "nodeGetBoundingBox splineNode splineNode.transform" in block
    assert '\\"bounds_available\\"' in block


def test_cli_compacts_alignment_output():
    source = APP.read_text(encoding="utf-8")
    assert 'send_command("GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT")' in source
    assert '"forest_alignment_properties"' in source
    assert '"bitmap_alignment_properties"' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.53"' in bridge or '\\"bridge_version\\":\\"0.9.53\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in runtime
