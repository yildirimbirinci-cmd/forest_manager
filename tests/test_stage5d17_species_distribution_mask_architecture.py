from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "app" / "species_distribution_mask_stage5d17.py"


def source() -> str:
    return APP.read_text(encoding="utf-8")


def test_stage_is_read_only():
    s = source()
    assert '"read_only": True' in s
    assert 'send_command("GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT")' in s
    assert "APPLY_" not in s
    assert "SET_" not in s


def test_semantic_probabilities_become_spatial_coverage():
    s = source()
    assert '"target_coverage_percent": probability' in s
    assert "coverage_basis" in s
    assert "original semantic species probability" in s


def test_density_units_are_not_reinterpreted():
    s = source()
    assert '"density_units_meters": 75.0' in s
    assert "density_meters_x" in s
    assert "density_meters_y" in s


def test_three_species_roles_are_explicit():
    s = source()
    assert "FM_Layer_01_foreground_mass" in s
    assert "FM_Layer_02_mid_accent" in s
    assert "FM_Layer_03_structural_shrub" in s


def test_mask_plan_uses_complementary_spatial_regions():
    s = source()
    assert "exclusive_primary_regions_with_soft_boundaries" in s
    assert "same_area_coordinate_space" in s
    assert "deterministic_seed" in s


def test_activation_is_deferred():
    s = source()
    assert '"prepared_layers_remain_disabled": True' in s
    assert '"legacy_forest_remains_active": True' in s
    assert "do not activate Forest layers yet" in s
