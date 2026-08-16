from forest_manager.site_model import ForestPackPlantingExecutionBridge, GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_bound_area_and_explicit_cluster_controls_compile_to_verified_operation_types():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "cluster",
        GeometryKind.REGION,
        [(0, 0), (5, 0), (5, 5), (0, 5)],
        closed=True,
        metadata={
            "forest_name": "FM_Forest_001",
            "forest_area_index": 2,
            "forest_area_threshold": 0.35,
            "forest_density_falloff": 1.25,
            "forest_cluster_size": 4.5,
            "forest_cluster_roughness": 0.4,
        },
    ))
    service.apply_artist_confirmation("cluster", SemanticRole.CLUSTER_ZONE)
    plan = PlantingPlanningService().build_plan(service)

    execution = ForestPackPlantingExecutionBridge().build_execution_plan(service, plan)
    targets = {(op.property_name, op.index): op.value for op in execution.operations}

    assert targets[("arthresholdlist", 2)] == 0.35
    assert targets[("arflafdenslist", 2)] == 1.25
    assert targets[("clusize", None)] == 4.5
    assert targets[("clurough", None)] == 0.4
    assert execution.blocked_directive_count == 0
