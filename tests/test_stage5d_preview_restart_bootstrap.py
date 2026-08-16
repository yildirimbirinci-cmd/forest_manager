from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "species_preview_bootstrap.py"
STAGE23 = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "single_layer_visual_preview_stage5d23.py"
STAGE24 = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "uv_clamp_visual_preview_stage5d24.py"


def test_bootstrap_preserves_protected_contracts():
    s = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'DENSITY_METERS = 75.0' in s
    assert 'GET_SPECIES_LAYER_CONTEXT' in s
    assert 'SET_DENSITY_METERS|' in s
    assert 'PREPARE_SPECIES_LAYER_FORESTS' in s
    assert 'generate_species_masks' in s
    assert 'BIND_SPECIES_DISTRIBUTION_MASKS|' in s


def test_bootstrap_refuses_to_invent_missing_scene_baseline():
    s = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'requires the saved FM_Forest_001 three-species baseline' in s
    assert 'arbitrary user selection' in s


def test_stage23_bootstraps_before_activation_but_not_rollback():
    s = STAGE23.read_text(encoding="utf-8")
    assert 'if not args.rollback:' in s
    assert 'ensure_species_preview_ready()' in s
    assert s.index('ensure_species_preview_ready()') < s.index('ACTIVATE_SINGLE_SPECIES_LAYER')


def test_stage24_bootstraps_before_uv_apply_but_not_rollback():
    s = STAGE24.read_text(encoding="utf-8")
    assert 'if not args.rollback:' in s
    assert 'ensure_species_preview_ready()' in s
    assert s.index('ensure_species_preview_ready()') < s.index('APPLY_SPECIES_UV_CLAMP_PREVIEW')
