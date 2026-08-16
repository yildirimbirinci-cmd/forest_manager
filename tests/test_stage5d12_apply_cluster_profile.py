from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "apply_cluster_profile_stage5d12.py"


def apply_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn applyNaturalClusterProfileJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_apply_command_is_exposed():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "APPLY_NATURAL_CLUSTER_PROFILE"' in source
    assert "applyNaturalClusterProfileJson()" in source


def test_apply_writes_only_verified_cluster_shape_parameters():
    block = apply_block()
    assert "forestNode.clurough = 35.0" in block
    assert "forestNode.cluedge = 25.0" in block
    assert "forestNode.clunoise = 10.0" in block
    assert "forestNode.divers = 2" not in block
    assert "forestNode.clusize =" not in block.split("if not verified then")[0]
    assert "forestNode.units_x =" not in block.split("if not verified then")[0]
    assert "forestNode.units_y =" not in block.split("if not verified then")[0]


def test_apply_has_rollback():
    block = apply_block()
    assert "if not verified then" in block
    assert "forestNode.clurough = oldClurough" in block
    assert "forestNode.cluedge = oldCluedge" in block
    assert "forestNode.clunoise = oldClunoise" in block
    assert 'throw "Cluster profile verification failed. Previous values restored."' in block


def test_density_and_probability_are_verified_and_preserved():
    block = apply_block()
    assert "oldUnitsX = forestNode.units_x" in block
    assert "oldUnitsY = forestNode.units_y" in block
    assert "oldProb = #()" in block
    assert "abs(forestNode.units_x - oldUnitsX)" in block
    assert "abs(forestNode.units_y - oldUnitsY)" in block
    assert "abs(forestNode.problist[i] - oldProb[i])" in block


def test_cli_uses_auto_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("APPLY_NATURAL_CLUSTER_PROFILE")' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.53"' in bridge or '\\"bridge_version\\":\\"0.9.53\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in runtime
