from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
CLI = (ROOT / "src" / "forest_manager" / "app" / "reload_bridge.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")

def test_bridge_supports_reload_command():
    assert 'pattern:"RELOAD_BRIDGE|*"' in BRIDGE
    assert "scheduleBridgeReload scriptPath" in BRIDGE
    assert "fileIn pathToLoad" in BRIDGE

def test_reload_is_deferred_until_after_response():
    assert "ForestManagerBridgeReloadTimer.Interval = 500" in BRIDGE
    assert "ForestManagerBridgeReloadTimer.Start()" in BRIDGE

def test_stop_cleans_reload_timer_listener_and_poll_timer():
    assert "ForestManagerBridgeReloadTimer.Stop()" in BRIDGE
    assert "ForestManagerBridgeReloadTimer.Dispose()" in BRIDGE
    assert "listener.Stop()" in BRIDGE
    assert "pollTimer.Dispose()" in BRIDGE

def test_shared_runtime_uses_project_bridge_file():
    assert 'project_root() / "maxscripts" / STAGED_BRIDGE_FILENAME' in RUNTIME
    assert '"RELOAD_BRIDGE|" + encoded' in RUNTIME

def test_shared_runtime_verifies_current_bridge_version():
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in RUNTIME
    assert "version == EXPECTED_BRIDGE_VERSION" in RUNTIME
    assert "bridge_version" in BRIDGE and "0.9.79" in BRIDGE

def test_reload_cli_delegates_to_shared_preflight():
    assert "ensure_current_bridge" in CLI
    assert "ensure_current_bridge()" in CLI
