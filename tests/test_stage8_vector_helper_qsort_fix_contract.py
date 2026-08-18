from pathlib import Path


def test_bridge_identity_and_no_nested_qsort_callback():
    root = Path(__file__).resolve().parents[1]
    main = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    staged = (root / "maxscripts" / "ForestManager_Bridge_0_9_88.ms").read_text(encoding="utf-8")
    assert main == staged
    assert '0.9.88' in main
    assert 'stage8-vector-region-helper-qsort-fix-20260818a' in main
    assert 'qsort names (fn a b = compare a b)' not in main
    assert 'fn fmStage8ListVectorHelpersJson sourceName' in main


def test_runtime_bridge_targets_0988_staged_bridge():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.88"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-vector-region-helper-qsort-fix-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_88.ms"' in text
