from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "apply_scale_stage5d4.py"


def apply_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn applyNativeScaleVariationJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_bridge_exposes_apply_native_scale_variation():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "APPLY_NATIVE_SCALE_VARIATION"' in source
    assert "applyNativeScaleVariationJson()" in source


def test_only_applyscale_is_directly_changed():
    block = apply_block()
    assert "forestNode.applyscale = true" in block
    forbidden_assignments = [
        "forestNode.scalexmin =",
        "forestNode.scalexmax =",
        "forestNode.scaleymin =",
        "forestNode.scaleymax =",
        "forestNode.scalezmin =",
        "forestNode.scalezmax =",
        "forestNode.applyrotation =",
        "forestNode.applytranslation =",
        "forestNode.units_x =",
        "forestNode.units_y =",
    ]
    for item in forbidden_assignments:
        assert item not in block


def test_protected_density_and_probabilities_are_verified():
    block = apply_block()
    assert "density X changed" in block
    assert "density Y changed" in block
    assert "probability values changed" in block


def test_native_scale_limits_are_preserved_and_verified():
    block = apply_block()
    assert "X scale limits changed" in block
    assert "Y scale limits changed" in block
    assert "Z scale limits changed" in block
    assert "scalelock changed" in block


def test_cli_requires_75_meter_density_to_remain_unchanged():
    source = APP.read_text(encoding="utf-8")
    assert '- 75.0' in source
    assert "density X changed" in source
    assert "density Y changed" in source


def test_bridge_and_preflight_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.54"' in bridge or '\\"bridge_version\\":\\"0.9.54\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in runtime
