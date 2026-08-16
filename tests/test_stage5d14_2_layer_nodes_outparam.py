from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"


def probe_block():
    source = BRIDGE.read_text(encoding="utf-8")
    start = source.index("fn getLiveSourceAreaContractJson")
    end = source.index("\n    ),", start)
    return source[start:end]


def test_layer_nodes_uses_byref_out_parameter():
    block = probe_block()
    assert "local layerNodes = #()" in block
    assert "refsLayer.nodes &layerNodes" in block
    assert "local layerNodes = refsLayer.nodes" not in block


def test_layer_nodes_call_is_guarded():
    block = probe_block()
    assert "local gotLayerNodes = false" in block
    assert "if gotLayerNodes do" in block


def test_probe_remains_read_only():
    block = probe_block()
    assert "setProperty" not in block
    assert '\\"read_only\\":true' in block


def test_managed_reference_filter_remains_intact():
    block = probe_block()
    assert 'getUserProp n "ForestManagerOwned"' in block
    assert "if owned do append managedRefs n" in block


def test_bridge_version_bumped():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.53"' in bridge or '\\"bridge_version\\":\\"0.9.53\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in runtime
