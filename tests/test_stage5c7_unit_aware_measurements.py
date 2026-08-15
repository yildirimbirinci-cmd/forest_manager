from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "selection_measurements_stage5c7.py"


def source():
    return BRIDGE.read_text(encoding="utf-8")


def test_selection_measurements_use_active_scene_formatter():
    s = source()
    assert "fn getSelectionMeasurementsJson" in s
    assert 'formatSystemValueForScene width' in s
    assert 'formatSystemValueForScene depth' in s
    assert 'formatSystemValueForScene height' in s
    assert '\\"scene_units\\":' in s


def test_t2_asset_dimensions_have_display_unit_outputs():
    s = source()
    assert '\\"source_width_display\\":' in s
    assert '\\"source_depth_display\\":' in s
    assert '\\"source_height_display\\":' in s


def test_reference_offset_reports_system_and_display_values():
    s = source()
    assert '\\"target_z_system_units\\":' in s
    assert '\\"target_z_display\\":' in s
    assert 'millimetersToSystemUnits -1500.0' in s


def test_density_units_have_display_formatted_outputs():
    s = source()
    assert '\\"units_x_display\\":' in s
    assert '\\"units_y_display\\":' in s


def test_new_measurement_command_is_routed():
    s = source()
    assert 'command == "GET_SELECTION_MEASUREMENTS"' in s
    assert 'getSelectionMeasurementsJson()' in s


def test_bridge_preflight_targets_0_9_15():
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.39"' in RUNTIME.read_text(encoding="utf-8")
    assert r'\"bridge_version\":\"0.9.39\"' in source()


def test_cli_uses_automatic_preflight():
    s = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in s
    assert 'send_command("GET_SELECTION_MEASUREMENTS")' in s
