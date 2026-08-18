from pathlib import Path


def test_ai_t2_resolution_contract_is_map_free_and_does_not_merge_scene_sources():
    resolver = Path("src/forest_manager/forest_control/ai_plant_group_resolution.py").read_text(encoding="utf-8")
    pipeline = Path("src/forest_manager/forest_control/official_planting_pipeline.py").read_text(encoding="utf-8")
    acceptance = Path("src/forest_manager/devtools/acceptance/stage8_ai_t2_resolution_acceptance.py").read_text(encoding="utf-8")
    assert "resolve_asset" in resolver
    assert "merge_missing_source" not in resolver
    assert "prepare_ai_candidates" in pipeline
    assert "parked_not_projected_from_reference_image" in pipeline
    assert "mutated_scene\": False" in acceptance
