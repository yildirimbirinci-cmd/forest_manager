from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "uv_clamp_visual_preview_stage5d24.py"


def function_block(name: str) -> str:
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn " + name)
    end = source.index("\n    ),", start)
    return source[start:end]


def _runtime_identity(runtime: str) -> tuple[str, str]:
    version = re.search(r'^EXPECTED_BRIDGE_VERSION = "([^"]+)"', runtime, re.MULTILINE)
    build_id = re.search(r'^EXPECTED_BRIDGE_BUILD_ID = "([^"]+)"', runtime, re.MULTILINE)
    assert version is not None
    assert build_id is not None
    return version.group(1), build_id.group(1)


def test_uv_normalization_helper_clamps_all_species_maps():
    helper = function_block("normalizeSpeciesDensityMapCoords coords")
    assert "coords.U_Tile = false" in helper
    assert "coords.V_Tile = false" in helper
    assert "coords.realWorldScale = false" in helper
    assert "coords.U_Tiling = 1.0" in helper
    assert "coords.V_Tiling = 1.0" in helper
    apply = function_block("applySpeciesUvClampPreviewJson")
    assert "normalizeSpeciesDensityMapCoords layerCoord" in apply


def test_apply_changes_preview_state_without_density_or_map_replacement():
    s = function_block("applySpeciesUvClampPreviewJson")
    assert "legacy.disabled = true" in s
    assert "layers[1].disabled = false" in s
    assert "layers[2].disabled = true" in s
    assert "layers[3].disabled = true" in s
    assert ".units_x =" not in s
    assert ".units_y =" not in s
    assert "\n        target.distmap =" not in s
    assert "\n        target.densityMap =" not in s
    assert "\n        target.distmode =" not in s


def test_apply_preserves_exact_75m_contract():
    s = function_block("applySpeciesUvClampPreviewJson")
    assert "abs((target.units_x / oneMeter) - 75.0)" in s
    assert "abs((target.units_y / oneMeter) - 75.0)" in s


def test_apply_is_transactional():
    s = function_block("applySpeciesUvClampPreviewJson")
    for token in ("oldUTile", "oldVTile", "oldLegacyDisabled", "oldLayerDisabled"):
        assert token in s
    assert "layerCoords[i].U_Tile = oldUTile[i]" in s
    assert "layerCoords[i].V_Tile = oldVTile[i]" in s
    assert "legacy.disabled = oldLegacyDisabled" in s
    assert "layers[i].disabled = oldLayerDisabled[i]" in s
    assert "\n            throw\n" in s


def test_rollback_restores_tiling_and_combined_forest():
    s = function_block("rollbackSpeciesUvClampPreviewJson")
    assert "layerCoord.U_Tile = true" in s
    assert "layerCoord.V_Tile = true" in s
    assert "legacy.disabled = false" in s
    assert "for layerNode in layers do layerNode.disabled = true" in s


def test_cli_has_apply_and_rollback_modes():
    s = APP.read_text(encoding="utf-8")
    assert "APPLY_SPECIES_UV_CLAMP_PREVIEW" in s
    assert "ROLLBACK_SPECIES_UV_CLAMP_PREVIEW" in s
    assert '"--rollback"' in s


def test_versions_match_current_runtime_identity():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    version, build_id = _runtime_identity(runtime)
    assert f'\\"bridge_version\\":\\"{version}\\"' in bridge
    assert f'\\"bridge_build_id\\":\\"{build_id}\\"' in bridge
