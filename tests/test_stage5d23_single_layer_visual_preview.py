from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "single_layer_visual_preview_stage5d23.py"


def activation_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn activateSingleSpeciesLayerPreviewJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def rollback_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn rollbackSpeciesLayerPreviewJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_activation_only_toggles_disabled_state():
    s = activation_block()
    assert "legacy.disabled = true" in s
    assert "layers[i].disabled = (i != layerIndex)" in s
    assert ".units_x =" not in s
    assert ".units_y =" not in s
    assert "\n            layerNode.distmap =" not in s
    assert "\n            layerNode.densityMap =" not in s
    assert "\n            layerNode.distmode =" not in s


def test_activation_requires_protected_75m_and_map_contract():
    s = activation_block()
    assert "abs(densityMetersX - 75.0)" in s
    assert "abs(densityMetersY - 75.0)" in s
    assert "layerNode.distmap == undefined" in s
    assert "layerNode.densityMap != true" in s
    assert "layerNode.distmode != 0" in s


def test_activation_is_transactional():
    s = activation_block()
    assert "oldLegacyDisabled" in s
    assert "oldLayerDisabled" in s
    assert "legacy.disabled = oldLegacyDisabled" in s
    assert "layers[i].disabled = oldLayerDisabled[i]" in s
    assert "\n            throw\n" in s


def test_rollback_restores_combined_forest_baseline():
    s = rollback_block()
    assert "legacy.disabled = false" in s
    assert "for layerNode in layers do layerNode.disabled = true" in s
    assert '\\"legacy_forest_active\\":true' in s
    assert '\\"all_species_layers_disabled\\":true' in s


def test_cli_defaults_to_foreground_layer_and_has_rollback():
    s = APP.read_text(encoding="utf-8")
    assert 'default=1' in s
    assert '"--rollback"' in s
    assert 'ACTIVATE_SINGLE_SPECIES_LAYER' in s
    assert 'ROLLBACK_SPECIES_LAYER_PREVIEW' in s



def _runtime_identity(runtime: str) -> tuple[str, str]:
    version = re.search(r'^EXPECTED_BRIDGE_VERSION = "([^"]+)"', runtime, re.MULTILINE)
    build_id = re.search(r'^EXPECTED_BRIDGE_BUILD_ID = "([^"]+)"', runtime, re.MULTILINE)
    assert version is not None
    assert build_id is not None
    return version.group(1), build_id.group(1)


def test_versions_match_current_runtime_identity():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    version, build_id = _runtime_identity(runtime)
    assert f'\\"bridge_version\\":\\"{version}\\"' in bridge
    assert f'\\"bridge_build_id\\":\\"{build_id}\\"' in bridge
