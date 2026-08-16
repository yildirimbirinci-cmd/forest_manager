from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SemanticRole,
    SiteModelIngestor,
    SiteModelService,
    SiteModelViewerInteraction,
)


def _service():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entity = ImportedEntity.create(
        source_id="site",
        entity_id="E1",
        kind="line",
        points=[(0, 0), (10, 0)],
        semantic_role="street_edge",
        semantic_confidence=0.8,
        label="Detected edge",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    return service


def test_assigning_same_ai_role_becomes_artist_confirmation():
    service = _service()
    interaction = SiteModelViewerInteraction(service)
    interaction.select(["cad:site:E1"])
    result = interaction.assign_role(SemanticRole.STREET_EDGE, notes="approved")
    assert result.annotations[0].source.value == "artist_confirmed"
    assert service.resolved_annotation("cad:site:E1").notes == "approved"


def test_assigning_different_role_becomes_artist_override_and_reject_maps_unknown():
    service = _service()
    interaction = SiteModelViewerInteraction(service)
    interaction.select(["cad:site:E1"])
    result = interaction.assign_role(SemanticRole.FRONT_BOUNDARY, notes="frontage")
    assert result.annotations[0].source.value == "artist_override"
    assert service.resolved_annotation("cad:site:E1").role is SemanticRole.FRONT_BOUNDARY

    rejected = interaction.reject_selected(notes="not a semantic edge")
    assert rejected.annotations[0].role is SemanticRole.UNKNOWN
    assert service.resolved_annotation("cad:site:E1").role is SemanticRole.UNKNOWN
