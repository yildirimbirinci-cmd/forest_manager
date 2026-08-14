from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
CLI = ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py"


def test_density_response_uses_normal_json_escaping():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'return "{\\"ok\\":true,\\"command\\":\\"SET_DENSITY_METERS\\",\\"data\\":" +' in source
    assert 'return "{\\\\\\"ok\\\\\\":true' not in source


def test_density_command_still_uses_exact_user_meter_value():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "local densityMeters = parts[2] as float" in source
    assert "configureDensityMetersJson densityMeters" in source


def test_cli_defaults_to_exact_75_meters():
    source = CLI.read_text(encoding="utf-8")
    assert 'parser.add_argument("--density-m", type=float, default=75.0)' in source


def test_cli_surfaces_raw_invalid_bridge_response():
    source = CLI.read_text(encoding="utf-8")
    assert "Invalid JSON from 3ds Max bridge:" in source


def test_bridge_version_is_0_9_10():
    source = BRIDGE.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.10\\"' in source
