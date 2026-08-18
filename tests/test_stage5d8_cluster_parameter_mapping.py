from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "cluster_mapping_stage5d8.py"


def mapping_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getClusterParameterMappingJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_bridge_exposes_mapping_command():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_CLUSTER_PARAMETER_MAPPING"' in source
    assert "getClusterParameterMappingJson()" in source


def test_mapping_targets_cluster_ui_related_terms():
    block = mapping_block()
    for term in ("cluster", "clump", "size", "rough", "blur", "noise", "edge", "div"):
        assert f'findString lowerName "{term}"' in block


def test_mapping_is_read_only():
    block = mapping_block()
    assert "setProperty" not in block
    assert "forestNode.divers =" not in block
    assert "forestNode.units_x =" not in block
    assert "forestNode.units_y =" not in block
    assert '\\"read_only\\":true' in block


def test_cli_uses_auto_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_CLUSTER_PARAMETER_MAPPING")' in source


def test_versions_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.79"' in bridge or '\\"bridge_version\\":\\"0.9.79\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime


def test_stage_does_not_hardcode_density():
    source = APP.read_text(encoding="utf-8")
    assert "75.0" not in source
