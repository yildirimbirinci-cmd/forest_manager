from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_bridge_contract_has_vector_area_species_binding_without_distribution_map():
    text = (_root() / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert r'\"bridge_version\":\"0.9.104\"' in text
    assert 'stage8-geometry-source-world-diagnostic-20260819a' in text
    assert 'FM_STAGE8_VECTOR_AREA_BIND' in text
    assert 'stage8VectorAreaBindingJson' in text
    assert 'forestNode.arselspeclist[areaIndex] = true' in text
    assert 'forestNode.arspeclist[areaIndex] = speciesSelections[helperIndex]' in text
    assert 'forestNode.pf_aractivelist[i] = false' in text
    assert '\\"distribution_map_used\\\":false' in text
    assert '\\"reference_image_coordinates_used\\\":false' in text


def test_runtime_bridge_targets_versioned_vector_area_bridge():
    text = (_root() / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.104"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_104.ms"' in text
    assert 'def bind_stage8_vector_region_areas(' in text
    assert 'FM_STAGE8_VECTOR_AREA_BIND' in text
