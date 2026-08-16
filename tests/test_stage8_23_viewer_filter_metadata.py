from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SiteModelService,
    SiteModelViewerBinding,
)


def test_binding_exposes_source_layer_and_page_metadata_for_ui_filters():
    source = ProjectSource("pdf", ProjectSourceKind.PDF, "plan.pdf", page_count=2)
    entities = (
        ImportedEntity.create(source_id="pdf", entity_id="A", kind="line", points=[(0, 0), (1, 0)], page_index=0, layer="Walls"),
        ImportedEntity.create(source_id="pdf", entity_id="B", kind="line", points=[(0, 1), (1, 1)], page_index=1, layer="Planting"),
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, entities))
    snapshot = SiteModelViewerBinding().build(service, source_id="pdf")
    assert snapshot.source_ids == ("pdf",)
    assert snapshot.layers == ("Planting", "Walls")
    assert snapshot.page_indexes == (0, 1)
