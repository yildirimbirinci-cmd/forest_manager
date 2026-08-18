from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "species_mask_deep_uvgen_contract_stage5d22.py"


def block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getSpeciesMaskDeepUvgenContractJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_probe_reads_distmap_coords_properties():
    s = block()
    assert "forestNode.distmap.coords" in s
    assert "getPropNames coords" in s
    assert "getProperty coords prop" in s


def test_probe_is_read_only():
    s = block()
    assert "setProperty" not in s
    assert "forestNode.offset_X =" not in s
    assert "forestNode.offset_Y =" not in s
    assert '\\"read_only\\":true' in s


def test_probe_reports_scene_unit_aware_spline_dimensions():
    s = block()
    assert 'units.decodeValue "1m"' in s
    assert '\\"width_meters\\"' in s
    assert '\\"height_meters\\"' in s
    assert '\\"center_x_meters\\"' in s
    assert '\\"center_y_meters\\"' in s


def test_cli_compacts_uvgen_properties():
    s = APP.read_text(encoding="utf-8")
    assert 'send_command("GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT")' in s
    assert "U_Offset" in s
    assert "V_Offset" in s
    assert "U_Tiling" in s
    assert "V_Tiling" in s


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.79"' in bridge or '\\"bridge_version\\":\\"0.9.79\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
