from pathlib import Path


def test_vector_area_bind_parses_original_case_command():
    text = Path("maxscripts/ForestManager_Bridge.ms").read_text(encoding="utf-8")
    marker = 'if matchPattern command pattern:"FM_STAGE8_VECTOR_AREA_BIND|*"'
    start = text.index(marker)
    block = text[start:start + 1200]
    assert 'filterString cleanCommand "|"' in block
    assert 'filterString command "|"' not in block


def test_bridge_identity_0_9_101():
    text = Path("maxscripts/ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert r'\"bridge_version\":\"0.9.102\"' in text
    assert 'stage8-vector-area-density-probability-fix-20260819a' in text
