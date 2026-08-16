from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "layer_density_contract_stage5d16.py"


def probe_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getLayerDensityDistributionContractJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_probe_targets_all_three_prepared_layers():
    block = probe_block()
    assert "FM_Layer_01_foreground_mass" in block
    assert "FM_Layer_02_mid_accent" in block
    assert "FM_Layer_03_structural_shrub" in block


def test_probe_is_read_only():
    block = probe_block()
    assert "setProperty" not in block
    assert "forestNode.disabled =" not in block
    assert "forestNode.units_x =" not in block
    assert "forestNode.units_y =" not in block
    assert '\\"read_only\\":true' in block


def test_probe_searches_density_distribution_weighting_terms():
    block = probe_block()
    for term in ("dens", "prob", "mult", "amount", "count", "item", "max", "percent", "ratio", "dist"):
        assert f'findString lowerName "{term}"' in block


def test_probe_reports_original_probability_metadata():
    block = probe_block()
    assert 'getUserProp forestNode "ForestManagerOriginalProbability"' in block
    assert '\\"original_probability\\"' in block


def test_cli_requires_disabled_75m_layers():
    source = APP.read_text(encoding="utf-8")
    assert 'send_command("GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT")' in source
    assert "if not layer.get(\"disabled\")" in source
    assert "75.0" in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.54"' in bridge or '\\"bridge_version\\":\\"0.9.54\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in runtime
