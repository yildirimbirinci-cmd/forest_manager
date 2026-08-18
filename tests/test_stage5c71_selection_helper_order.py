from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"


def source():
    return BRIDGE.read_text(encoding="utf-8")


def test_get_single_selection_is_defined_before_measurement_function():
    s = source()
    assert s.index("fn getSingleSelection =") < s.index("fn getSelectionMeasurementsJson =")


def test_measurement_function_calls_defined_helper():
    s = source()
    start = s.index("fn getSelectionMeasurementsJson =")
    end = s.index("fn getSelectionData obj =", start)
    block = s[start:end]
    assert "local node = getSingleSelection()" in block


def test_bridge_version_is_0_9_16():
    assert 'bridge_version' in source() and '0.9.79' in source()


def test_runtime_preflight_expects_0_9_16():
    s = RUNTIME.read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in s
