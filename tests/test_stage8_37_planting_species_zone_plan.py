from forest_manager.site_model import (
    AnnotationSource,
    GeometryKind,
    PlantingIntentKind,
    PlantingPlanningService,
    SemanticRole,
    SiteModelService,
    create_geometry,
)


def test_artist_species_zone_becomes_high_priority_species_directive_with_species_metadata():
    service = SiteModelService()
    service.upsert_geometry(
        create_geometry(
            "species-zone",
            GeometryKind.REGION,
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            closed=True,
            metadata={"species": ["Lavandula angustifolia", "Salvia nemorosa"]},
        )
    )
    service.apply_ai_annotation("species-zone", SemanticRole.PLANTING_BED, confidence=0.8)
    service.apply_artist_override("species-zone", SemanticRole.SPECIES_ZONE, notes="Artist species palette")

    plan = PlantingPlanningService().build_plan(service)
    directive = plan.directive_for("species-zone")

    assert directive is not None
    assert directive.intent is PlantingIntentKind.SPECIES
    assert directive.source is AnnotationSource.ARTIST_OVERRIDE
    assert directive.species == ("Lavandula angustifolia", "Salvia nemorosa")
    assert directive.notes == "Artist species palette"
    assert plan.artist_directive_count == 1
