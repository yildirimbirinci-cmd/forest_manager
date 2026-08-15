from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
CLI = ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"

def density_command_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index('SET_DENSITY_METERS requires density in meters.')
    return source[start:start + 900]

def test_density_response_wrapper_is_normal_json_shape():
    block = density_command_block()
    assert "SET_DENSITY_METERS" in block
    assert "configureDensityMetersJson densityMeters" in block
    assert '"error"' in block or '\\"error\\":' in block

def test_density_command_still_uses_exact_user_meter_value():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "local densityMeters = parts[2] as float" in source
    assert "configureDensityMetersJson densityMeters" in source

def test_cli_defaults_to_exact_75_meters():
    source = CLI.read_text(encoding="utf-8")
    assert 'parser.add_argument("--density-m", type=float, default=75.0)' in source

def test_shared_runtime_surfaces_raw_invalid_bridge_response():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "Invalid JSON from 3ds Max bridge:" in source

def test_bridge_version_matches_current_contract():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "bridge_version" in source and "0.9.39" in source
