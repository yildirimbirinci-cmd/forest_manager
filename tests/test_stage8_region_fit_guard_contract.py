from pathlib import Path


def test_vector_area_binding_contains_region_footprint_guard():
    text = Path("src/forest_manager/forest_control/vector_area_binding.py").read_text(encoding="utf-8")
    assert "_apply_region_footprint_guard" in text
    assert "source_footprint_exceeds_region_fit_limit" in text
    assert "wall_band_meters" in text
    assert "walkway_band_meters" in text
    assert "get_geometry_source_world_diagnostic" in text
