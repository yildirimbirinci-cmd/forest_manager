from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def test_street_anchor_allows_unlabelled_front_boundary_to_be_inferred_from_site_context():
    service = SiteModelService()
    service.upsert_geometry(create_geometry("street", GeometryKind.LINE, [(0, 0), (100, 0)]))
    service.upsert_geometry(create_geometry("front", GeometryKind.POLYLINE, [(0, 5), (100, 5)]))
    service.upsert_geometry(create_geometry("rear", GeometryKind.POLYLINE, [(0, 100), (100, 100)]))
    service.upsert_geometry(create_geometry("left", GeometryKind.POLYLINE, [(0, 5), (0, 100)]))
    service.apply_artist_confirmation("street", SemanticRole.STREET_EDGE)

    pipeline = SemanticClassificationPipeline()
    pipeline.analyze(service)

    front = [a for a in service.annotations_for("front") if a.source.value == "ai_inferred"][-1]
    assert front.role is SemanticRole.FRONT_BOUNDARY
    assert front.reason == "site_context_frontage_adjacency"
    assert front.confidence >= 0.8
