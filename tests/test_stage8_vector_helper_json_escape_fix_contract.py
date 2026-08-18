from pathlib import Path


def test_helper_commands_emit_normal_bridge_json_not_double_escaped():
    root = Path(__file__).resolve().parents[1]
    text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert '0.9.90' in text
    assert 'stage8-vector-region-helper-json-escape-fix-20260818a' in text
    start = text.index('fn fmStage8ListVectorHelpersJson')
    end = text.index('if matchPattern command pattern:"FM_STAGE8_DELETE_VECTOR_HELPER|*"')
    block = text[start:end + 800]
    assert '{\\\\\"source_node_name' not in block
    assert '{\\\\\"helper_name' not in block
    assert 'return "{\\\\\"ok' not in block
    assert '"{\\\"source_node_name\\\":\\\""' in block
    assert '"{\\\"helper_name\\\":\\\""' in block
    assert 'return "{\\\"ok\\\":true' in block


def test_runtime_expects_09090_staged_bridge():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'src/forest_manager/max_bridge/runtime_bridge.py').read_text(encoding='utf-8')
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.90"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-vector-region-helper-json-escape-fix-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_90.ms"' in text


def test_main_and_staged_bridge_are_identical():
    root = Path(__file__).resolve().parents[1]
    assert (root/'maxscripts/ForestManager_Bridge.ms').read_bytes() == (root/'maxscripts/ForestManager_Bridge_0_9_90.ms').read_bytes()
