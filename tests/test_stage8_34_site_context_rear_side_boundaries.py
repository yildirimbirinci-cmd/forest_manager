from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def test_context_distinguishes_rear_and_side_boundaries_relative_to_confirmed_frontage():
    service = SiteModelService()
    for geometry in (
        create_geometry("street", GeometryKind.LINE, [(0, 0), (100, 0)]),
        create_geometry("front", GeometryKind.POLYLINE, [(0, 5), (100, 5)]),
        create_geometry("rear", GeometryKind.POLYLINE, [(0, 100), (100, 100)]),
        create_geometry("side", GeometryKind.POLYLINE, [(0, 5), (0, 100)]),
    ):
        service.upsert_geometry(geometry)
    service.apply_artist_confirmation("street", SemanticRole.STREET_EDGE)

    SemanticClassificationPipeline().analyze(service)

    rear = [a for a in service.annotations_for("rear") if a.source.value == "ai_inferred"][-1]
    side = [a for a in service.annotations_for("side") if a.source.value == "ai_inferred"][-1]
    assert rear.role is SemanticRole.REAR_BOUNDARY
    assert rear.reason == "site_context_opposite_frontage"
    assert side.role is SemanticRole.SIDE_BOUNDARY
    assert side.reason == "site_context_lateral_envelope"
