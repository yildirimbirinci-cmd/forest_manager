from forest_manager.site_model import ForestPackPlantingExecutionBridge, GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_keep_clear_maps_existing_area_record_to_exclude_mode():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "clear", GeometryKind.REGION, [(0, 0), (4, 0), (4, 4), (0, 4)], closed=True,
        metadata={"forest_name": "FM_Forest_001", "forest_area_index": 2},
    ))
    service.apply_artist_confirmation("clear", SemanticRole.KEEP_CLEAR)
    plan = ForestPackPlantingExecutionBridge().build_execution_plan(service, PlantingPlanningService().build_plan(service))
    assert plan.blocked == ()
    operation = next(op for op in plan.operations if op.label == "clear.area[2].include_exclude")
    assert operation.property_name == "arincexclist"
    assert operation.index == 2
    assert operation.value == 1
