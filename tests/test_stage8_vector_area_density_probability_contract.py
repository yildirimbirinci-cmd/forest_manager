from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_vector_area_handler_applies_explicit_scene_unit_density_and_active_probabilities():
    text = (_root() / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert "fn stage8VectorAreaBindingJson forestName sourceName bindingPayload densityMeters" in text
    assert "local densitySystemUnits = metersToSystemUnits densityMeters" in text
    assert "forestNode.units_x = densitySystemUnits" in text
    assert "forestNode.units_y = densitySystemUnits" in text
    assert "local activeProbability = 100.0 / activeSpeciesIds.count" in text
    assert "forestNode.problist[geometryIndex] = probability" in text
    assert r'\"density_meters\"' in text
    assert r'\"active_species_count\"' in text
    assert 'if parts.count != 5 do throw "FM_STAGE8_VECTOR_AREA_BIND requires forest, source, binding payload and density tokens."' in text
    assert 'local densityMeters = parts[5] as float' in text
    assert 'stage8VectorAreaBindingJson forestName sourceName bindingPayload densityMeters' in text


def test_python_binding_defaults_to_verified_point_75_meter_baseline():
    text = (_root() / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "density_meters: float = 0.75" in text
    assert 'format(float(density_meters), ".12g")' in text
