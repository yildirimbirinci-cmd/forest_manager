from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
STAGE = ROOT / "src" / "forest_manager" / "app" / "restore_species_baseline_stage5d25.py"
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"


def test_bridge_auto_start_loader_contract() -> None:
    text = RUNTIME.read_text(encoding="utf-8")
    assert 'AUTO_STARTUP_FILENAME = "ForestManager_AutoBridge.ms"' in text
    assert "def install_startup_bridge_loader()" in text
    assert "fileIn fmBridgePath quiet:true" in text
    assert "startup_paths = install_startup_bridge_loader()" in text


def test_stage5d25_restart_state_contract() -> None:
    text = STAGE.read_text(encoding="utf-8")
    assert 'STATE_FILENAME = "stage5d25_recovery.json"' in text
    assert 'Path(local_appdata) / "ForestManager" / "state"' in text
    assert '"interrupted"' in text and '_save_state(' in text
    assert '_save_state("completed", "verified", report=report)' in text
    assert "rebuilding the verified baseline idempotently" in text


def test_density_and_bridge_identity_contract() -> None:
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.41\\"' in bridge
    assert '\\"bridge_build_id\\":\\"stage5d25-density-restartsafe-20260815a\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.41"' in runtime
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage5d25-density-restartsafe-20260815a"' in runtime
    assert "build_id == EXPECTED_BRIDGE_BUILD_ID" in runtime
    assert '\\"density_meters_x\\":' in bridge
    assert '\\"density_meters_y\\":' in bridge
    assert 'density.get("density_meters_x")' in STAGE.read_text(encoding="utf-8")
