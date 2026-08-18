from pathlib import Path


def test_bridge_contract_contains_read_only_geometry_source_diagnostic():
    text = Path("maxscripts/ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert "0.9.104" in text
    assert "FM_STAGE8_GET_GEOMETRY_SOURCE_WORLD_DIAGNOSTIC" in text
    assert "getStage8GeometrySourceWorldDiagnosticJson" in text
    assert "nodeGetBoundingBox sourceNode sourceNode.transform" in text
    assert "sourceNode.objectOffsetPos" in text
    assert "sourceNode.objectOffsetScale" in text
    assert "read_only" in text


def test_runtime_contract_uses_base64_tokens():
    text = Path("src/forest_manager/max_bridge/runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.104"' in text
    assert "def get_geometry_source_world_diagnostic" in text
    assert '_encode_token(forest)' in text
    assert '_encode_token(csv)' in text
