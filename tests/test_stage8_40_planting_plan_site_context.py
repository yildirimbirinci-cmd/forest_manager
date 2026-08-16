from forest_manager.site_model import GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_planting_directive_carries_nearby_confirmed_boundary_context_without_changing_artist_role():
    service = SiteModelService()
    service.upsert_geometry(create_geometry("front", GeometryKind.LINE, [(0, 0), (100, 0)]))
    service.upsert_geometry(
        create_geometry("bed", GeometryKind.REGION, [(35, 2), (65, 2), (65, 10), (35, 10)], closed=True)
    )
    service.apply_artist_confirmation("front", SemanticRole.FRONT_BOUNDARY)
    service.apply_artist_confirmation("bed", SemanticRole.PLANTING_BED)

    directive = PlantingPlanningService().build_plan(service).directive_for("bed")

    assert directive is not None
    assert directive.semantic_role is SemanticRole.PLANTING_BED
    assert SemanticRole.FRONT_BOUNDARY in directive.boundary_context
    assert "boundary_context=front_boundary" in directive.evidence
