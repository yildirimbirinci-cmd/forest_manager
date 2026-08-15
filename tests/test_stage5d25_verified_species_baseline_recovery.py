from pathlib import Path


def test_stage5d25_contract_source_contains_verified_species_and_safety_sequence():
    source = Path("src/forest_manager/app/restore_species_baseline_stage5d25.py").read_text(encoding="utf-8")
    assert "Lavandula angustifolia 'Hidcote' (Lavender)" in source
    assert "Butomus umbellatus (Flowering rush )" in source
    assert "Bush_Berberis" in source
    assert "RESET_MANAGED_FOREST_FROM_SELECTION" in source
    assert "SET_GEOMETRY_PROBABILITIES|42.8571,28.57145,28.57145" in source
    assert "SET_DENSITY_METERS|75.0" in source
    assert "PREPARE_SPECIES_LAYER_FORESTS" in source
    assert "BIND_SPECIES_DISTRIBUTION_MASKS" in source
    assert "APPLY_SPECIES_UV_CLAMP_PREVIEW" not in source


def test_stage5d25_uses_actual_selection_spline_area_contract_fields():
    source = Path("src/forest_manager/app/restore_species_baseline_stage5d25.py").read_text(encoding="utf-8")
    assert 'selection.get("spline_count")' in source
    assert 'selection.get("all_splines_closed")' in source
    assert 'selection.get("node_name")' in source
    assert 'selection.get("verified")' in source
    assert 'selection.get("is_spline")' not in source
    assert 'selection.get("is_closed")' not in source
