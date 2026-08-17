from pathlib import Path


def test_plant_group_handlers_preserve_case_sensitive_base64_tokens():
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8-sig")

    upsert = bridge.split('if matchPattern command pattern:"FM_PLANT_GROUP_AREA_UPSERT|*"', 1)[1]
    upsert = upsert.split('if matchPattern command pattern:"FM_PLANT_GROUP_AREA_FINALIZE|*"', 1)[0]
    finalize = bridge.split('if matchPattern command pattern:"FM_PLANT_GROUP_AREA_FINALIZE|*"', 1)[1]
    finalize = finalize.split('if matchPattern command pattern:', 1)[0]

    assert 'filterString cleanCommand "|"' in upsert
    assert 'filterString command "|"' not in upsert
    assert 'filterString cleanCommand "|"' in finalize
    assert 'filterString command "|"' not in finalize


def test_python_expects_fixed_bridge_identity():
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-versioned-bridge-no-watcher-20260817a"' in runtime
