from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"src"/"forest_manager"/"app"/"ensure_three_layer_runtime_stage5d30.py").read_text(encoding="utf-8")
def test_stage5d30_contract():
    for token in ("ROLLBACK_SPECIES_LAYER_PREVIEW","CONFIGURE_SPECIES_MAP_PROJECTION","ACTIVATE_ALL_SPECIES_LAYERS","SET_ALL_FOREST_POINT_CLOUD","75.0"): assert token in APP
    assert "render_settings_changed" in APP and "point_cloud_vmesh" in APP
