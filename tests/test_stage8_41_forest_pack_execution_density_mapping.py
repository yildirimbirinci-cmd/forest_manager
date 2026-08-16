from forest_manager.site_model import (
    ForestPackPlantingExecutionBridge,
    GeometryKind,
    PlantingPlanningService,
    SemanticRole,
    SiteModelService,
    create_geometry,
)


def test_explicit_density_units_map_exactly_without_implicit_conversion():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "bed",
        GeometryKind.REGION,
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        closed=True,
        metadata={"forest_name": "FM_Forest_001", "forest_distribution_density_units": 75.0},
    ))
    service.apply_artist_confirmation("bed", SemanticRole.PLANTING_BED)
    planting_plan = PlantingPlanningService().build_plan(service)

    execution = ForestPackPlantingExecutionBridge().build_execution_plan(service, planting_plan)
    values = {(op.property_name, op.index): op.value for op in execution.operations}

    assert values[("units_x", None)] == 75.0
    assert values[("units_y", None)] == 75.0
    assert execution.blocked_directive_count == 0
