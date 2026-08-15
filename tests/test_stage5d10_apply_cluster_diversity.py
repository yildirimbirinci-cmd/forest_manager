from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "apply_clusters_stage5d10.py"


def apply_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn applyClusterDiversityModeJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_bridge_exposes_apply_command():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "APPLY_CLUSTER_DIVERSITY_MODE"' in source
    assert "applyClusterDiversityModeJson()" in source


def test_apply_changes_only_diversity_mode():
    block = apply_block()
    assert "forestNode.divers = 2" in block
    for forbidden in (
        "forestNode.clusize =", "forestNode.clurough =", "forestNode.clunoise =",
        "forestNode.cluedge =", "forestNode.units_x =", "forestNode.units_y =",
        "forestNode.problist[i] =", "forestNode.applyscale =", "forestNode.applyrotation =",
        "forestNode.applytranslation =",
    ):
        assert forbidden not in block


def test_apply_verifies_protected_state():
    block = apply_block()
    for token in ("density X changed", "density Y changed", "probability values changed", "applyscale changed", "rotation changed", "translation changed", "cluster size changed", "roughness changed", "noise changed", "blurry edge changed"):
        assert token in block


def test_apply_rolls_back_diversity_on_failure():
    block = apply_block()
    assert "forestNode.divers = diversityBefore" in block


def test_cli_uses_automatic_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("APPLY_CLUSTER_DIVERSITY_MODE")' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert 'bridge_version' in bridge and '0.9.39' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.39"' in runtime
