from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SiteModelService,
    SiteModelViewerBinding,
)


def test_render_record_preserves_annotation_source_confidence_label_and_notes():
    source = ProjectSource("pdf", ProjectSourceKind.PDF, "plan.pdf", page_count=1)
    entity = ImportedEntity.create(
        source_id="pdf",
        entity_id="P1",
        kind="polyline",
        points=[(0, 0), (10, 0), (10, 10)],
        page_index=0,
        semantic_role="planting_bed",
        semantic_confidence=0.91,
        label="Bed A",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    record = SiteModelViewerBinding().build(service).records[0]
    assert record.annotation_source.value == "ai_inferred"
    assert record.confidence == 0.91
    assert record.label == "Bed A"
    assert "Imported semantic candidate" in record.notes
    assert record.artist_confirmed is False
