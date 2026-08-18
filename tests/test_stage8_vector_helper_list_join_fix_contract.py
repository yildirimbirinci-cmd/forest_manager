from pathlib import Path


def test_bridge_identity_and_list_join_are_self_contained():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'maxscripts' / 'ForestManager_Bridge.ms').read_text(encoding='utf-8')
    assert '\\"bridge_version\\":\\"0.9.89\\"' in text
    assert 'stage8-vector-region-helper-list-join-fix-20260818a' in text
    block = text[text.index('fn fmStage8ListVectorHelpersJson'):text.index('fn fmStage8RoleWireColor')]
    assert 'joinStrings' not in block
    assert 'local joined = ""' in block
    assert 'joined += items[i]' in block


def test_runtime_expects_exact_staged_bridge():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'src' / 'forest_manager' / 'max_bridge' / 'runtime_bridge.py').read_text(encoding='utf-8')
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.89"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-vector-region-helper-list-join-fix-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_89.ms"' in text


def test_main_and_staged_bridge_are_identical():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'maxscripts' / 'ForestManager_Bridge.ms').read_bytes() == (root / 'maxscripts' / 'ForestManager_Bridge_0_9_89.ms').read_bytes()
