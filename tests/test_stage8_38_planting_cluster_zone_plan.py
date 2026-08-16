from forest_manager.site_model import GeometryKind, PlantingIntentKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


def test_cluster_zone_preserves_artist_group_and_density_hints_for_generation():
    service = SiteModelService()
    service.upsert_geometry(
        create_geometry(
            "cluster-zone",
            GeometryKind.REGION,
            [(20, 20), (35, 20), (35, 32), (20, 32)],
            closed=True,
            metadata={"plant_group": "Mediterranean shrub cluster", "density_hint": "dense"},
        )
    )
    service.apply_artist_confirmation("cluster-zone", SemanticRole.CLUSTER_ZONE)

    directive = PlantingPlanningService().build_plan(service).directive_for("cluster-zone")

    assert directive is not None
    assert directive.intent is PlantingIntentKind.CLUSTER
    assert directive.cluster_label == "Mediterranean shrub cluster"
    assert directive.density_hint == "dense"
    assert directive.artist_authored is True
