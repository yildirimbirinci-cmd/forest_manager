from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"src"/"forest_manager"/"devtools"/"legacy"/"clustered_three_layer_composition_stage5d31.py").read_text(encoding="utf-8")
GEN=(ROOT/"src"/"forest_manager"/"placement"/"species_mask_generator.py").read_text(encoding="utf-8")
def test_cluster_policy_and_order():
    assert "def generate_species_cluster_masks(" in GEN and "deterministic_species_cluster_masks_v2" in GEN
    expected=["ROLLBACK_SPECIES_LAYER_PREVIEW","BIND_SPECIES_DISTRIBUTION_MASKS","CONFIGURE_SPECIES_MAP_PROJECTION","ACTIVATE_ALL_SPECIES_LAYERS","SET_ALL_FOREST_POINT_CLOUD"]
    positions=[APP.index(v) for v in expected]; assert positions==sorted(positions)
def test_density_render_contract():
    assert "75.0" in APP and "render_settings_changed" in APP and "point_cloud_vmesh" in APP
