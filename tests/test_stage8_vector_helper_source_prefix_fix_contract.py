from pathlib import Path


def test_bridge_source_prefix_uses_literal_alphanumeric_membership():
    root = Path(__file__).resolve().parents[1]
    text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert 'local allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"' in text
    assert '(findString allowed ch) != undefined' in text
    assert 'pattern:"[A-Za-z0-9_]"' not in text


def test_bridge_and_runtime_identity_are_0_9_91():
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert ',\\"bridge_version\\":\\"0.9.91\\"' in bridge
    assert 'stage8-vector-region-helper-source-prefix-fix-20260818a' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.91"' in runtime
    assert 'ForestManager_Bridge_0_9_91.ms' in runtime
