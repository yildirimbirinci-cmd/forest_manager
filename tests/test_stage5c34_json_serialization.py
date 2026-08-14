from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
CLI = ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py"


def density_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn configureDensityMetersJson densityMeters =")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_density_payload_has_single_json_escape_layer():
    block = density_block()
    assert '"{\\\\\\"forest_name' not in block
    assert '"{\\"forest_name' in block
    assert ',\\"density_m\\":' in block
    assert ',\\"verified\\":true}' in block


def test_outer_density_response_wrapper_is_valid_json_shape():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'return "{\\"ok\\":true,\\"command\\":\\"SET_DENSITY_METERS\\",\\"data\\":" +' in source
    assert 'return "{\\\\\\"ok\\\\\\":true' not in source


def test_exact_75_meter_default_is_preserved():
    source = CLI.read_text(encoding="utf-8")
    assert 'default=75.0' in source


def test_meter_to_system_unit_conversion_is_unchanged():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'local oneMeterSystemUnits = units.decodeValue "1m"' in source
    assert "local densitySystemUnits = oneMeterSystemUnits * densityMeters" in source


def test_generated_item_probe_is_preserved():
    source = BRIDGE.read_text(encoding="utf-8")
    assert '\\"generated_items_after\\":' in source
    assert '\\"generated_count_probe\\":\\"trees.count\\"' in source


def test_bridge_version_is_0_9_11():
    source = BRIDGE.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.11"' in source or '\\"bridge_version\\":\\"0.9.11\\"' in source
