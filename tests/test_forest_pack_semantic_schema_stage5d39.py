from forest_manager.forest_control.schema import find_semantic_field, raw_property_coverage, semantic_domains, semantic_fields


def test_stage5d39_domain_contract():
    domains = semantic_domains()
    assert len(domains) == 11
    assert [d.name for d in domains] == [
        "geometry", "distribution", "areas", "transform", "surface", "camera", "material", "animation", "display", "collision", "effects"
    ]


def test_stage5d39_curve_boundary_is_preserved():
    assert find_semantic_field("surface", "surface_falloff_curves").access == "read_only_opaque"
    assert find_semantic_field("camera", "camera_curves").access == "read_only_opaque"
    assert find_semantic_field("effects", "effect_curves").access == "read_only_opaque"


def test_stage5d39_atomic_array_contracts():
    assert find_semantic_field("geometry", "sources").access == "atomic_adapter_required"
    assert find_semantic_field("areas", "area_records").access == "area_record_adapter"


def test_stage5d39_raw_coverage_contract():
    coverage = raw_property_coverage(["globscale", "distmap", "unknown_property"])
    assert coverage["available_count"] == 3
    assert coverage["covered_count"] == 2
    assert coverage["covered"] == ["distmap", "globscale"]
    assert coverage["undeclared"] == ["unknown_property"]
    assert coverage["declared_count"] == len({raw for field in semantic_fields() for raw in field.raw_properties})
