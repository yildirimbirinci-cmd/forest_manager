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


def test_viewer_artist_correction_is_saved_and_restored(tmp_path):
    source = ProjectSource("pdf", ProjectSourceKind.PDF, "garden.pdf", page_count=1)
    entity = ImportedEntity.create(
        source_id="pdf",
        entity_id="R1",
        kind="region",
        points=[(0, 0), (4, 0), (4, 4)],
        closed=True,
        page_index=0,
        semantic_role="lawn",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    path = tmp_path / "site_model.json"
    interaction = SiteModelViewerInteraction(service, persistence_path=path)
    interaction.select(["pdf:pdf:p0:R1"])
    interaction.assign_role(SemanticRole.PLANTING_BED, label="Perennial bed", notes="artist correction")

    restored = SiteModelService()
    restored.load(path)
    annotation = restored.resolved_annotation("pdf:pdf:p0:R1")
    assert annotation.role is SemanticRole.PLANTING_BED
    assert annotation.source.value == "artist_override"
    assert annotation.label == "Perennial bed"
    assert annotation.notes == "artist correction"
