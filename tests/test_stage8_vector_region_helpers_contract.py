from pathlib import Path
import inspect
from forest_manager.forest_control import vector_region_helpers
from forest_manager.max_bridge import runtime_bridge


def test_runtime_bridge_identity_and_helper_commands():
    assert runtime_bridge.EXPECTED_BRIDGE_VERSION == "0.9.86"
    assert runtime_bridge.STAGED_BRIDGE_FILENAME == "ForestManager_Bridge_0_9_86.ms"
    source=inspect.getsource(runtime_bridge.upsert_stage8_vector_region_helper)
    assert "FM_STAGE8_UPSERT_VECTOR_HELPER" in source


def test_bridge_has_managed_vector_helper_contract():
    bridge=Path(__file__).resolve().parents[1]/"maxscripts"/"ForestManager_Bridge.ms"
    text=bridge.read_text(encoding="utf-8")
    assert '\\"bridge_version\\":\\"0.9.86\\"' in text
    assert "FM_STAGE8_UPSERT_VECTOR_HELPER" in text
    assert "FM_STAGE8_LIST_VECTOR_HELPERS" in text
    assert "FM_STAGE8_DELETE_VECTOR_HELPER" in text
    assert 'pattern:"FM_Region_*"' in text
