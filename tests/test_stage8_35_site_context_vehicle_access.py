from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def test_closed_area_connecting_frontage_and_building_is_inferred_as_driveway():
    service = SiteModelService()
    service.upsert_geometry(create_geometry("street", GeometryKind.LINE, [(0, 0), (100, 0)]))
    service.upsert_geometry(create_geometry("building", GeometryKind.REGION, [(40, 28), (60, 28), (60, 48), (40, 48)], closed=True))
    service.upsert_geometry(create_geometry("access", GeometryKind.REGION, [(46, 2), (54, 2), (54, 30), (46, 30)], closed=True))
    service.apply_artist_confirmation("street", SemanticRole.STREET_EDGE)
    service.apply_artist_confirmation("building", SemanticRole.BUILDING_EDGE)

    SemanticClassificationPipeline().analyze(service)

    result = [a for a in service.annotations_for("access") if a.source.value == "ai_inferred"][-1]
    assert result.role is SemanticRole.DRIVEWAY
    assert result.reason == "site_context_vehicle_access_connector"
    assert "aspect_ratio=" in " ".join(result.evidence)
