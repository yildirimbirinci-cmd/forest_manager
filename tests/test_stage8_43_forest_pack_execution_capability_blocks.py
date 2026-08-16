from forest_manager.site_model import ExecutionBlockReason, ForestPackPlantingExecutionBridge, GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_species_requires_explicit_source_binding_but_keep_clear_uses_verified_area_mode_switch():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "species",
        GeometryKind.REGION,
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        closed=True,
        metadata={"forest_name": "FM_Forest_001", "species": ["Lavandula angustifolia"]},
    ))
    service.upsert_geometry(create_geometry(
        "clear",
        GeometryKind.REGION,
        [(5, 0), (8, 0), (8, 3), (5, 3)],
        closed=True,
        metadata={"forest_name": "FM_Forest_001", "forest_area_index": 1},
    ))
    service.apply_artist_confirmation("species", SemanticRole.SPECIES_ZONE)
    service.apply_artist_confirmation("clear", SemanticRole.KEEP_CLEAR)

    execution = ForestPackPlantingExecutionBridge().build_execution_plan(service, PlantingPlanningService().build_plan(service))
    reasons = {item.geometry_id: item.reason for item in execution.blocked}

    assert reasons["species"] is ExecutionBlockReason.SPECIES_SOURCE_ASSIGNMENT_UNAVAILABLE
    assert "clear" not in reasons
    assert not any(op.label.startswith("species.") for op in execution.operations)
    clear_mode = [op for op in execution.operations if op.label == "clear.area[1].include_exclude"]
    assert len(clear_mode) == 1
    assert clear_mode[0].property_name == "arincexclist"
    assert clear_mode[0].value == 1
