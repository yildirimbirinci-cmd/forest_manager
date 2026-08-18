from pathlib import Path


def test_provider_is_loopback_only_and_map_free():
    source = Path("src/forest_manager/site_model/local_vision_provider.py").read_text(encoding="utf-8")
    assert "127.0.0.1:8089" in source
    assert "must use a loopback endpoint" in source
    assert "species_candidates" in source
    assert "source_names" in source
    reference = Path("src/forest_manager/site_model/reference_image.py").read_text(encoding="utf-8")
    assert "def analyze_with_provider" in reference
    assert "from_group_intents" in reference
