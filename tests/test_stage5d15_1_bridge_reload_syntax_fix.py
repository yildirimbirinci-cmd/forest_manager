from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"


def split_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn prepareSpeciesLayerForestsJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_transaction_catch_uses_bare_rethrow():
    block = split_block()
    assert "throw message" not in block
    assert "local message = getCurrentException()" not in block
    assert "\n            throw\n" in block


def test_cleanup_still_happens_before_rethrow():
    block = split_block()
    cleanup = block.index("for node in created do")
    rethrow = block.index("\n            throw\n", cleanup)
    assert cleanup < rethrow


def test_versions_match_0931():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "0.9.53" in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in runtime
