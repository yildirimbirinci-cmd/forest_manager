from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"


def test_semantic_apply_does_not_enter_parked_diversity_map_pipeline():
    source = CONTROLLER.read_text(encoding="utf-8")

    assert "refresh_plant_group_diversity_map" not in source
    assert 'artist_values[field] = edit.value' in source
    assert 'self.scene_state.write_verified(' in source
    assert '"naturalness", "cluster_character"' in source
    assert "Diversity-map generation is intentionally parked" in source
