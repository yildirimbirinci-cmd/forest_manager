from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "src" / "forest_manager" / "devtools" / "acceptance" / "official_runtime_acceptance.py"


def test_official_acceptance_uses_stable_runtime_gateways():
    source = RUNNER.read_text(encoding="utf-8")

    assert "ForestSceneRuntime" in source
    assert "SceneStateGateway" in source
    assert "ForestPackControlService" in source
    assert "UnitConversionGateway" in source
    assert "ForestManagerUIController" in source

    assert "scene_state.read_manifest(preflight=False)" in source
    assert "scene_runtime.execute_manifest(manifest, strict_acceptance=False)" in source
    assert source.count("scene_runtime.execute_manifest(manifest, strict_acceptance=False)") == 2


def test_official_acceptance_covers_current_stability_milestones():
    source = RUNNER.read_text(encoding="utf-8")

    required_checks = (
        "bridge_identity",
        "manifest_has_executable_groups",
        "single_primary_forest_contract",
        "manifest_execution_verified_twice",
        "geometry_sources_idempotent",
        "active_scene_unit_roundtrip",
        "fresh_controller_scene_reconstruction",
        "fresh_controller_pending_empty",
        "fresh_controller_selection_clean",
    )
    for check in required_checks:
        assert check in source


def test_official_acceptance_keeps_map_path_parked():
    source = RUNNER.read_text(encoding="utf-8")

    assert "stage8_diversity_map_semantic_acceptance" not in source
    assert "refresh_plant_group_diversity_map" not in source
    assert '"map_policy": "parked_not_part_of_official_acceptance"' in source
