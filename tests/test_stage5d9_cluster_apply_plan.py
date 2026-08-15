from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "app" / "cluster_plan_stage5d9.py"


def test_plan_uses_verified_cluster_diversity_mode():
    source = APP.read_text(encoding="utf-8")
    assert "CLUSTERS_DIVERSITY_MODE = 2" in source


def test_plan_requires_exact_cluster_properties():
    source = APP.read_text(encoding="utf-8")
    for name in ("clusize", "clurough", "clunoise", "cluedge", "divers"):
        assert f'"{name}"' in source


def test_plan_is_read_only():
    source = APP.read_text(encoding="utf-8")
    assert '"read_only": True' in source
    assert 'send_command("GET_CLUSTER_PARAMETER_MAPPING")' in source
    assert 'send_command("GET_COMPOSITION_CONTEXT")' in source
    assert "SET_" not in source
    assert "APPLY_" not in source


def test_plan_changes_only_diversity_mode():
    source = APP.read_text(encoding="utf-8")
    assert '"change_only": ["divers: 0 -> 2"]' in source


def test_plan_preserves_density_and_probabilities():
    source = APP.read_text(encoding="utf-8")
    assert '"75.0 m density"' in source
    assert '"geometry probabilities"' in source


def test_auto_preflight_is_used():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
