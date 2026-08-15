from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"


def test_get_species_preview_nodes_is_defined_before_uv_clamp_callers():
    source = BRIDGE.read_text(encoding="utf-8")
    helper = source.index("fn getSpeciesPreviewNodes")
    apply_fn = source.index("fn applySpeciesUvClampPreviewJson")
    rollback_fn = source.index("fn rollbackSpeciesUvClampPreviewJson")
    assert helper < apply_fn
    assert helper < rollback_fn


def test_uv_clamp_functions_still_call_shared_helper():
    source = BRIDGE.read_text(encoding="utf-8")
    apply_start = source.index("fn applySpeciesUvClampPreviewJson")
    apply_end = source.index("\n    ),", apply_start)
    rollback_start = source.index("fn rollbackSpeciesUvClampPreviewJson")
    rollback_end = source.index("\n    ),", rollback_start)
    assert "getSpeciesPreviewNodes()" in source[apply_start:apply_end]
    assert "getSpeciesPreviewNodes()" in source[rollback_start:rollback_end]



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
