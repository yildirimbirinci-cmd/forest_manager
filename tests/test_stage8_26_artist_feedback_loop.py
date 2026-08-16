from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def _geometry(identifier: str):
    return create_geometry(
        identifier, GeometryKind.POLYLINE, [(0, 0), (5, 0)],
        metadata={"source_layer": "LANDSCAPE_ZONE_A", "project_source_kind": "cad"},
    )


def test_artist_override_becomes_reusable_feedback_without_losing_artist_priority():
    service = SiteModelService()
    service.upsert_geometry(_geometry("g1"))
    service.upsert_geometry(_geometry("g2"))
    service.apply_ai_annotation("g1", SemanticRole.UNKNOWN, confidence=0.2)
    service.apply_artist_override("g1", SemanticRole.PLANTING_BED)

    pipeline = SemanticClassificationPipeline()
    result = pipeline.analyze(service, ["g1", "g2"])

    assert result.feedback_rule_count == 1
    assert service.resolved_annotation("g1").role is SemanticRole.PLANTING_BED
    assert service.resolved_annotation("g1").source.value == "artist_override"
    g2 = service.resolved_annotation("g2")
    assert g2.role is SemanticRole.PLANTING_BED
    assert g2.reason == "artist_feedback"
    assert g2.confidence == 0.98
