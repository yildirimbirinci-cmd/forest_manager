from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "composition_context_stage5c9.py"


def test_composition_context_is_read_only_runtime_command():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_COMPOSITION_CONTEXT"' in source
    assert '"read_only\\\":true' in source or '\\"read_only\\":true' in source


def test_context_combines_real_spline_area_and_scene_units():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "getSelectionSplineAreaJson()" in source
    assert "getSceneUnitsJson()" in source


def test_context_combines_geometry_and_probabilities():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "getForestGeometrySummaryJson()" in source
    assert '\\"geometry\\":' in source


def test_density_is_inferred_from_active_scene_unit_conversion():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "local oneMeterSystemUnits = metersToSystemUnits 1.0" in source
    assert "local densityMetersX = unitsX / oneMeterSystemUnits" in source
    assert "local densityMetersY = unitsY / oneMeterSystemUnits" in source


def test_stage_does_not_set_density_or_probabilities():
    app_source = APP.read_text(encoding="utf-8")
    assert 'send_command("GET_COMPOSITION_CONTEXT")' in app_source
    assert "SET_DENSITY" not in app_source
    assert "SET_GEOMETRY_PROBABILITIES" not in app_source


def test_cli_uses_automatic_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source


def test_bridge_version_matches_preflight():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '0.9.79' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
