from pathlib import Path

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


def test_versions_match_0939():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "0.9.39" in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.39"' in runtime
