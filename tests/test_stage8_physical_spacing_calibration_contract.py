from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "maxscripts" / "ForestManager_Bridge.ms"
RUNTIME = ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py"
ACCEPTANCE = ROOT / "src" / "forest_manager" / "devtools" / "acceptance" / "stage8_vector_area_species_binding_acceptance.py"


def test_bridge_converts_physical_spacing_to_distribution_scale():
    text = BRIDGE.read_text(encoding="utf-8")
    assert "spacingSystemUnits = metersToSystemUnits densityMeters" in text
    assert "distributionPixelsX" in text
    assert "distributionPixelsY" in text
    assert "distributionUnitsX = spacingSystemUnits * distributionPixelsX" in text
    assert "distributionUnitsY = spacingSystemUnits * distributionPixelsY" in text
    assert "forestNode.units_x = distributionUnitsX" in text
    assert "forestNode.units_y = distributionUnitsY" in text


def test_bridge_reports_spacing_and_distribution_pixels():
    text = BRIDGE.read_text(encoding="utf-8")
    assert 'physical_spacing_meters' in text
    assert 'distribution_pixels_x' in text
    assert 'distribution_pixels_y' in text


def test_runtime_identity_is_0105():
    text = RUNTIME.read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.105"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_105.ms"' in text
    assert 'stage8-physical-spacing-calibration-20260819a' in text


def test_acceptance_checks_physical_spacing_semantics():
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert '"name": "physical_spacing_exactly_applied"' in text
    assert 'distribution_pixels_x' in text
    assert 'distribution_pixels_y' in text
