from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
RUNTIME = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
DENSITY = (ROOT / "src" / "forest_manager" / "app" / "density_stage5c3.py").read_text(encoding="utf-8")

def test_current_bridge_identity_is_single_source_of_truth():
    assert "bridge_version" in BRIDGE and "0.9.53" in BRIDGE
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.53"' in RUNTIME

def test_exact_75_meter_density_contract_is_preserved():
    assert "default=75.0" in DENSITY
    assert "SET_DENSITY_METERS" in BRIDGE
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in BRIDGE

def test_scene_units_are_runtime_detected():
    for token in ("units.DisplayType", "units.MetricType", "units.SystemType", "units.SystemScale"):
        assert token in BRIDGE
    assert 'command == "GET_SCENE_UNITS"' in BRIDGE

def test_unit_sensitive_runtime_commands_are_present():
    for command in ("GET_SELECTION_MEASUREMENTS", "GET_SELECTION_SPLINE_AREA", "GET_COMPOSITION_CONTEXT"):
        assert command in BRIDGE

def test_managed_scene_reset_remains_idempotent():
    assert 'setUserProp node "ForestManagerOwned" "true"' in BRIDGE
    assert "deleteManagedReferenceNodes" in BRIDGE
    assert "collectManagedForestSourceNodes" in BRIDGE
