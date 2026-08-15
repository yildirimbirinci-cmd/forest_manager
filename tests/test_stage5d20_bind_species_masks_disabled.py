from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "bind_species_masks_stage5d20.py"


def bind_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn bindSpeciesDistributionMasksJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_binding_uses_bitmaptexture_and_distmap():
    block = bind_block()
    assert "Bitmaptexture filename:maskPaths[i]" in block
    assert "forestNode.distmap = bitmapMap" in block
    assert "forestNode.densityMap = true" in block
    assert "forestNode.distmode = 0" in block


def test_density_units_are_preserved():
    block = bind_block()
    assert "oldUnitsX" in block
    assert "oldUnitsY" in block
    assert "forestNode.units_x = oldUnitsX[i]" in block
    assert "forestNode.units_y = oldUnitsY[i]" in block


def test_layers_remain_disabled_and_legacy_is_not_modified():
    block = bind_block()
    assert "forestNode.disabled = true" in block
    assert 'getNodeByName "FM_Forest_001"' in block
    assert "legacyForest.disabled =" not in block


def test_binding_rolls_back_on_failure():
    block = bind_block()
    assert "forestNode.distmap = oldDistmaps[i]" in block
    assert "forestNode.densityMap = oldDensityMaps[i]" in block
    assert "forestNode.distmode = oldDistmodes[i]" in block
    assert "\n            throw\n" in block


def test_cli_uses_soft_masks_only():
    source = APP.read_text(encoding="utf-8")
    assert "FM_Mask_01_foreground_mass.png" in source
    assert "FM_Mask_02_mid_accent.png" in source
    assert "FM_Mask_03_structural_shrub.png" in source
    assert "_primary.png" not in source


def test_cli_requires_disabled_densitymap_75m_contract():
    source = APP.read_text(encoding="utf-8")
    assert 'if not layer.get("disabled")' in source
    assert 'if not layer.get("densityMap")' in source
    assert "75.0" in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.34"' in bridge or '\\"bridge_version\\":\\"0.9.34\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.34"' in runtime
