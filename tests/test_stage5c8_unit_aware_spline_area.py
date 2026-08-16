from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
APP = ROOT / "src" / "forest_manager" / "app" / "spline_area_stage5c8.py"


def test_bridge_exposes_spline_area_command():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'command == "GET_SELECTION_SPLINE_AREA"' in source
    assert "getSelectionSplineAreaJson()" in source


def test_area_uses_sampled_closed_spline_geometry():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "sampledClosedSplineAreaSystemSquared" in source
    assert "interpCurve3D node splineIndex t" in source
    assert "cross points[i] points[j]" in source
    assert "sampling_steps_per_spline\\\":512" in source


def test_area_is_normalized_to_square_meters_from_active_scene_units():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'local oneMeterSystemUnits = units.decodeValue "1m"' in source
    assert "areaSquareMeters = totalAreaSystemSquared / (oneMeterSystemUnits * oneMeterSystemUnits)" in source


def test_metric_display_area_context_is_runtime_driven():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "getDisplayAreaUnitContext" in source
    assert 'units.decodeValue "1mm"' in source
    assert 'units.decodeValue "1cm"' in source
    assert 'units.decodeValue "1m"' in source
    assert 'units.decodeValue "1km"' in source


def test_cli_uses_automatic_bridge_preflight():
    source = APP.read_text(encoding="utf-8")
    assert "ensure_current_bridge()" in source
    assert 'send_command("GET_SELECTION_SPLINE_AREA")' in source


def test_bridge_version_and_preflight_match():
    bridge = BRIDGE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '"bridge_version":"0.9.54"' in bridge or '\\"bridge_version\\":\\"0.9.54\\"' in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in runtime


def test_no_density_value_is_changed_in_this_stage():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "configureDensityMetersJson densityMeters" in source
    app_source = APP.read_text(encoding="utf-8")
    assert "density" not in app_source.lower()
