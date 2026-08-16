from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, create_geometry


def test_layer_metadata_drives_semantic_classification():
    geometry = create_geometry(
        "g1", GeometryKind.POLYLINE, [(0, 0), (10, 0)],
        metadata={"source_layer": "FRONT_BOUNDARY", "project_source_kind": "cad"},
    )
    result = SemanticClassificationPipeline().classify_geometry(geometry)
    assert result.role is SemanticRole.FRONT_BOUNDARY
    assert result.confidence >= 0.75
    assert result.reason == "source_metadata_match"
    assert result.evidence
