from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "src" / "forest_manager" / "forest_control" / "official_planting_pipeline.py"
MANIFEST = ROOT / "src" / "forest_manager" / "forest_control" / "runtime_manifest.py"


def test_official_stage8_pipeline_does_not_import_forward_scene_executor_or_map_runtime():
    pipeline = PIPELINE.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")
    combined = pipeline + manifest

    assert "Stage8PlantingPlanSceneExecutor" not in combined
    assert "stage8_scene_execution" not in combined
    assert "refresh_plant_group_diversity_map" not in combined
    assert "zone_mask_path" not in manifest
    assert "scene_runtime.execute_manifest(" in pipeline


def test_spacing_is_explicit_scene_space_policy_not_reference_image_projection():
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert "spacing_system_by_group" in manifest
    assert "primary_boundary.node_name" in manifest
    assert "Reference-image pixel masks" in manifest
    assert "image dimensions" in manifest
