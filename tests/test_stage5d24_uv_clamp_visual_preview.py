from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "uv_clamp_visual_preview_stage5d24.py"


def apply_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn applySpeciesUvClampPreviewJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def rollback_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn rollbackSpeciesUvClampPreviewJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_apply_changes_only_tile_and_disabled_state():
    s = apply_block()
    assert "coords.U_Tile = false" in s
    assert "coords.V_Tile = false" in s
    assert "legacy.disabled = true" in s
    assert "layers[1].disabled = false" in s
    assert ".units_x =" not in s
    assert ".units_y =" not in s
    assert "\n        target.distmap =" not in s
    assert "\n        target.densityMap =" not in s
    assert "\n        target.distmode =" not in s


def test_apply_preserves_exact_75m_contract():
    s = apply_block()
    assert "abs((target.units_x / oneMeter) - 75.0)" in s
    assert "abs((target.units_y / oneMeter) - 75.0)" in s


def test_apply_is_transactional():
    s = apply_block()
    assert "oldUTile" in s
    assert "oldVTile" in s
    assert "oldLegacyDisabled" in s
    assert "oldLayerDisabled" in s
    assert "coords.U_Tile = oldUTile" in s
    assert "coords.V_Tile = oldVTile" in s
    assert "\n            throw\n" in s


def test_rollback_restores_tiling_and_combined_forest():
    s = rollback_block()
    assert "coords.U_Tile = true" in s
    assert "coords.V_Tile = true" in s
    assert "legacy.disabled = false" in s
    assert "for layerNode in layers do layerNode.disabled = true" in s


def test_cli_has_apply_and_rollback_modes():
    s = APP.read_text(encoding="utf-8")
    assert "APPLY_SPECIES_UV_CLAMP_PREVIEW" in s
    assert "ROLLBACK_SPECIES_UV_CLAMP_PREVIEW" in s
    assert '"--rollback"' in s


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.39"' in bridge or '\\"bridge_version\\":\\"0.9.39\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.39"' in runtime
