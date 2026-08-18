from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_bridge_identity_and_runtime_handoff_are_0_9_87():
    bridge = (ROOT / 'maxscripts' / 'ForestManager_Bridge.ms').read_text(encoding='utf-8')
    runtime = (ROOT / 'src' / 'forest_manager' / 'max_bridge' / 'runtime_bridge.py').read_text(encoding='utf-8')
    assert '0.9.87' in bridge
    assert 'stage8-vector-region-helper-struct-fix-20260818a' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.87"' in runtime
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-vector-region-helper-struct-fix-20260818a"' in runtime
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_87.ms"' in runtime


def test_inserted_struct_functions_are_comma_separated():
    text = (ROOT / 'maxscripts' / 'ForestManager_Bridge.ms').read_text(encoding='utf-8')
    names = [
        'fmStage8VectorHelperPrefix',
        'fmStage8ListVectorHelpersJson',
        'fmStage8RoleWireColor',
        'fmStage8UpsertVectorHelperJson',
        'fmStage8DeleteVectorHelperJson',
    ]
    for current, nxt in zip(names, names[1:] + ['handleCommand']):
        start = text.index('fn ' + current)
        end = text.index('fn ' + nxt, start)
        block = text[start:end]
        assert re.search(r'\n    \),\s*$', block), f'{current} is missing struct separator comma'


def test_main_and_staged_bridge_are_identical_and_bom_free():
    main = (ROOT / 'maxscripts' / 'ForestManager_Bridge.ms').read_bytes()
    staged = (ROOT / 'maxscripts' / 'ForestManager_Bridge_0_9_87.ms').read_bytes()
    assert main == staged
    assert not main.startswith(b'\xef\xbb\xbf')
