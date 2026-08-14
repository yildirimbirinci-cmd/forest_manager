from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
CLI = (ROOT / "src" / "forest_manager" / "app" / "reload_bridge.py").read_text(encoding="utf-8")


def test_bridge_supports_reload_command():
    assert 'pattern:"RELOAD_BRIDGE|*"' in BRIDGE
    assert "scheduleBridgeReload scriptPath" in BRIDGE
    assert "fileIn pathToLoad" in BRIDGE


def test_reload_is_deferred_until_after_response():
    assert "reloadTimer.Interval = 250" in BRIDGE
    assert "reloadTimer.Start()" in BRIDGE


def test_stop_cleans_reload_timer_listener_and_poll_timer():
    assert "reloadTimer.Stop()" in BRIDGE
    assert "reloadTimer.Dispose()" in BRIDGE
    assert "listener.Stop()" in BRIDGE
    assert "pollTimer.Dispose()" in BRIDGE


def test_reload_cli_uses_project_bridge_file():
    assert 'project_root() / "maxscripts" / "ForestManager_Bridge.ms"' in CLI
    assert 'send_raw("RELOAD_BRIDGE|" + encoded)' in CLI


def test_reload_cli_verifies_new_bridge_version():
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.13"' in CLI
    assert 'send_raw("PING"' in CLI
    assert "version == EXPECTED_BRIDGE_VERSION" in CLI


def test_bridge_version_is_0_9_13():
    assert '\\"bridge_version\\":\\"0.9.13\\"' in BRIDGE
