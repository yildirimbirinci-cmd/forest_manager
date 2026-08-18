from pathlib import Path

def test_vector_helper_upsert_uses_defined_bool_json_helper():
    bridge = Path(__file__).resolve().parents[1] / "maxscripts" / "ForestManager_Bridge.ms"
    text = bridge.read_text(encoding="utf-8")
    assert "+ boolJson created +" in text
    assert "+ jsonBool created +" not in text
    assert 'stage8-vector-helper-response-bool-fix-20260818a' in text
