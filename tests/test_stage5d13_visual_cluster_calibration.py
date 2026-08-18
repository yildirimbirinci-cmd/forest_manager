from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "cluster_visual_calibration_stage5d13.py"


def apply_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn applyVisualClusterCalibrationJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_profile_targets_match_visual_calibration():
    source = APP.read_text(encoding="utf-8")
    assert "TARGET_CLUSTER_SIZE_METERS = 30.0" in source
    assert "TARGET_ROUGHNESS_PERCENT = 25.0" in source
    assert "TARGET_BLURRY_EDGE_PERCENT = 20.0" in source
    assert "TARGET_NOISE_PERCENT = 5.0" in source


def test_preview_is_default_and_apply_is_explicit():
    source = APP.read_text(encoding="utf-8")
    assert 'parser.add_argument("--apply", action="store_true")' in source
    assert "return _apply() if args.apply else _preview()" in source


def test_cluster_size_conversion_is_runtime_unit_aware():
    block = apply_block()
    assert 'units.decodeValue "1m"' in block
    assert "local targetClusterSize = oneMeter * 30.0" in block
    assert "3000.0" not in block


def test_apply_changes_only_cluster_parameters_before_verification():
    block = apply_block()
    before_verify = block.split("local verified = true")[0]
    assert "forestNode.clusize = targetClusterSize" in before_verify
    assert "forestNode.clurough = 25.0" in before_verify
    assert "forestNode.cluedge = 20.0" in before_verify
    assert "forestNode.clunoise = 5.0" in before_verify
    assert "forestNode.units_x =" not in before_verify
    assert "forestNode.units_y =" not in before_verify
    assert "forestNode.divers =" not in before_verify


def test_apply_verifies_protected_state_and_rolls_back():
    block = apply_block()
    assert "abs(forestNode.units_x - oldUnitsX)" in block
    assert "abs(forestNode.units_y - oldUnitsY)" in block
    assert "abs(forestNode.problist[i] - oldProb[i])" in block
    assert "if not verified then" in block
    assert "forestNode.clusize = oldClusize" in block
    assert "forestNode.clurough = oldClurough" in block
    assert "forestNode.cluedge = oldCluedge" in block
    assert "forestNode.clunoise = oldClunoise" in block


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.79"' in bridge or '\\"bridge_version\\":\\"0.9.79\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
