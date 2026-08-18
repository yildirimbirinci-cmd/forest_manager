from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"src"/"forest_manager"/"forest_control"/"plant_group_execution.py"


def test_visible_execution_uses_scene_polygon_and_color_id_map():
    source=SOURCE.read_text(encoding="utf-8")
    assert "_build_visible_scene_space_map(" in source
    assert "_apply_species_color_ids(forest_name, plans, svc)" in source
    assert "bind_single_forest_diversity_map(" in source
    assert '"reference_image_projection": False' in source
    assert 'map_source_kind = "selected_3ds_max_boundary_semantic_regions"' in source


def test_visible_execution_no_longer_clears_distmap_for_stage8():
    source=SOURCE.read_text(encoding="utf-8")
    execution=source[source.index("def execute_plant_group_manifest("):]
    assert '"map_pipeline_deferred"' not in execution
    assert '"distmap",\n        None' not in execution
