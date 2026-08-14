from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
DENSITY = ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py"
UNITS = ROOT / "src" / "forest_manager" / "app" / "scene_units_stage5c4.py"
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"


def test_shared_runtime_targets_latest_bridge():
    source = RUNTIME.read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.14"' in source
    assert '"RELOAD_BRIDGE|" + encoded' in source
    assert "ensure_current_bridge" in source


def test_density_command_runs_bridge_preflight_automatically():
    source = DENSITY.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert "send_command" in source
    assert "default=75.0" in source


def test_scene_units_command_runs_bridge_preflight_automatically():
    source = UNITS.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_SCENE_UNITS")' in source


def test_preflight_does_not_reload_when_version_already_current():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "if version == EXPECTED_BRIDGE_VERSION" in source


def test_first_upgrade_error_is_explicit():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "older than 0.9.13" in source
    assert "run maxscripts/ForestManager_Bridge.ms once" in source


def test_bridge_version_is_0_9_14():
    source = BRIDGE.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.14\\"' in source
