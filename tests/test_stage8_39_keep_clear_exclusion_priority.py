from forest_manager.site_model import GeometryKind, PlantingIntentKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_keep_clear_is_emitted_as_first_class_exclusion_and_sorts_before_planting_directives():
    service = SiteModelService()
    service.upsert_geometry(create_geometry("bed", GeometryKind.REGION, [(0, 0), (20, 0), (20, 20), (0, 20)], closed=True))
    service.upsert_geometry(create_geometry("clear", GeometryKind.REGION, [(5, 5), (8, 5), (8, 8), (5, 8)], closed=True))
    service.apply_ai_annotation("bed", SemanticRole.PLANTING_BED, confidence=0.9)
    service.apply_artist_override("clear", SemanticRole.KEEP_CLEAR)

    plan = PlantingPlanningService().build_plan(service)

    assert plan.directives[0].geometry_id == "clear"
    assert plan.directives[0].intent is PlantingIntentKind.EXCLUSION
    assert plan.directives[0].blocks_planting is True
    assert plan.exclusion_geometry_ids == ("clear",)
    assert plan.directive_for("bed").intent is PlantingIntentKind.PLANTING_BED
