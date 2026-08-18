from pathlib import Path


def test_official_pipeline_keeps_source_lifecycle_separate_from_manifest_execution():
    source = Path("src/forest_manager/forest_control/official_planting_pipeline.py").read_text(encoding="utf-8")
    assert "def inspect_scene_sources(" in source
    assert "def ensure_scene_sources(" in source
    assert "def execute(" in source
    execute_block = source[source.index("    def execute("):]
    assert "merge_resolved_asset(" not in execute_block


def test_source_listing_uses_verified_geometry_name_array():
    source = Path("src/forest_manager/forest_control/stage8_asset_resolution.py").read_text(encoding="utf-8")
    assert '"namelist"' in source
    assert "def list_geometry_source_names(" in source
    assert "def merge_resolved_asset(" in source
