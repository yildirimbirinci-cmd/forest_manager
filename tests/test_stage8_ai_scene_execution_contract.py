from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "src" / "forest_manager" / "devtools" / "acceptance" / "stage8_ai_scene_execution_acceptance.py"


def _source() -> str:
    return ACCEPTANCE.read_text(encoding="utf-8")


def test_acceptance_uses_only_official_scene_runtime_facade():
    source = _source()

    assert "from forest_manager.forest_control.scene_runtime import ForestSceneRuntime" in source
    assert "from forest_manager.forest_control.scene_state import SceneStateGateway" in source
    assert "stage8_scene_execution" not in source
    assert "Stage8PlantingPlanSceneExecutor" not in source
    assert source.count("scene_runtime.execute_manifest(") == 2


def test_acceptance_chains_existing_ai_t2_source_reuse_step():
    source = _source()

    assert 'SOURCE_REUSE_MODULE = "forest_manager.devtools.acceptance.stage8_ai_source_reuse_acceptance"' in source
    assert '"--reference-image"' in source
    assert '"ai_t2_source_reuse_verified"' in source


def test_acceptance_contract_covers_required_scene_invariants():
    source = _source()

    required_tokens = (
        "only_resolved_groups_selected_for_execution",
        "geometry_source_count_unchanged",
        "allium_allamanda_preserved",
        "no_duplicate_geometry_sources",
        "second_execution_idempotent",
        "map_policy_parked",
        "cobjlist",
        "namelist",
    )
    for token in required_tokens:
        assert token in source
