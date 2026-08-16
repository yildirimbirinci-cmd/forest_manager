from forest_manager.site_model import ForestPackPlantingExecutionBridge, GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_species_source_insertion_requires_explicit_scene_node_binding():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "species", GeometryKind.REGION, [(0, 0), (4, 0), (4, 4), (0, 4)], closed=True,
        metadata={
            "forest_name": "FM_Forest_001",
            "species": ["Lavandula angustifolia"],
            "forest_source_node_names": ["FM_SRC_Lavandula", "FM_SRC_Lavandula"],
        },
    ))
    service.apply_artist_confirmation("species", SemanticRole.SPECIES_ZONE)
    plan = ForestPackPlantingExecutionBridge().build_execution_plan(service, PlantingPlanningService().build_plan(service))
    assert plan.blocked == ()
    assert [(item.forest_name, item.source_node_name) for item in plan.source_insertions] == [("FM_Forest_001", "FM_SRC_Lavandula")]
