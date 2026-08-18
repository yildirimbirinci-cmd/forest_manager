from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
STAGE = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "restore_species_baseline_stage5d25.py"
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"


def _runtime_identity(runtime: str) -> tuple[str, str]:
    version = re.search(r'^EXPECTED_BRIDGE_VERSION = "([^"]+)"', runtime, re.MULTILINE)
    build_id = re.search(r'^EXPECTED_BRIDGE_BUILD_ID = "([^"]+)"', runtime, re.MULTILINE)
    assert version is not None
    assert build_id is not None
    return version.group(1), build_id.group(1)


def test_bridge_auto_start_loader_contract() -> None:
    text = RUNTIME.read_text(encoding="utf-8")
    assert 'AUTO_STARTUP_FILENAME = "ForestManager_AutoBridge.ms"' in text
    assert "def install_startup_bridge_loader()" in text
    assert "fileIn fmBridgePath quiet:true" in text
    assert "def _disable_startup_loaders()" in text


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
    version, build_id = _runtime_identity(runtime)
    assert f'\\"bridge_version\\":\\"{version}\\"' in bridge
    assert f'\\"bridge_build_id\\":\\"{build_id}\\"' in bridge
    assert "build_id == EXPECTED_BRIDGE_BUILD_ID" in runtime
    assert "density_meters_x" in bridge
    assert "density_meters_y" in bridge
    stage = STAGE.read_text(encoding="utf-8")
    assert 'density.get("density_meters_x")' in stage
    assert 'density.get("density_meters_y")' in stage
