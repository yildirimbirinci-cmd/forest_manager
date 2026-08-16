from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
CLI = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "density_stage5c3.py"

def density_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn configureDensityMetersJson densityMeters =")
    end = source.index("\n    ),", start)
    return source[start:end]

def density_command_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index('SET_DENSITY_METERS requires density in meters.')
    return source[start:start + 900]

def test_density_payload_has_single_json_object_shape():
    block = density_block()
    assert "forest_name" in block
    assert "density_m" in block
    assert "verified" in block

def test_outer_density_response_wrapper_uses_payload_and_error_fields():
    block = density_command_block()
    assert "SET_DENSITY_METERS" in block
    assert "configureDensityMetersJson densityMeters" in block
    assert "error" in block

def test_exact_75_meter_default_is_preserved():
    assert "default=75.0" in CLI.read_text(encoding="utf-8")

def test_meter_to_system_unit_conversion_uses_shared_runtime_helper():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "local oneMeterSystemUnits = metersToSystemUnits 1.0" in source
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in source

def test_generated_item_probe_is_reported():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "generated_items_after" in source
    assert "generated_count_probe" in source
    assert "trees.count" in source

def test_bridge_version_matches_current_contract():
    assert "0.9.54" in BRIDGE.read_text(encoding="utf-8")
