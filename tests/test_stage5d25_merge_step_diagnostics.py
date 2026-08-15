from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"

def test_stage5d25_merge_diagnostics_and_source_name_are_present() -> None:
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.40"' in runtime
    assert "local expectedSourceName = getFilenameFile assetPath" in bridge
    assert "MERGE_STEP[mergeMAXFile]" in bridge
    assert "MERGE_STEP[newObjects]" in bridge
    assert "MERGE_STEP[chooseMergedSourceNode]" in bridge
    assert "MERGE_STEP[prepareReferenceNode]" in bridge
    assert "MERGE_STEP[bindForestGeometrySource]" in bridge

def test_verified_merge_contract_is_preserved() -> None:
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "mergeMAXFile assetPath #select #autoRenameDups #useMergedMtlDups quiet:true" in bridge
    assert "chooseMergedSourceNode newObjects expectedSourceName:expectedSourceName" in bridge
    assert "prepareReferenceNode sourceNode" in bridge
    assert "bindForestGeometrySource forestNode sourceNode" in bridge
