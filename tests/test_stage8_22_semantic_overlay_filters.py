from forest_manager.site_model import (
    AnnotationSource,
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SiteModelService,
    SiteViewerPresenter,
)


def test_semantic_overlay_can_hide_ai_without_deleting_annotations():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entity = ImportedEntity.create(
        source_id="site",
        entity_id="E1",
        kind="line",
        points=[(0, 0), (1, 0)],
        semantic_role="front_boundary",
        semantic_confidence=0.9,
    )
    service = SiteModelService()
    result = SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    presenter = SiteViewerPresenter(service)

    assert len(presenter.snapshot().records) == 1
    presenter.set_annotation_source_visible(AnnotationSource.AI_INFERRED, False)
    assert presenter.snapshot().records == ()
    assert service.resolved_annotation(result.geometry_ids[0]).source is AnnotationSource.AI_INFERRED


def test_artist_override_remains_visible_when_ai_overlay_is_hidden():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entity = ImportedEntity.create(
        source_id="site",
        entity_id="E1",
        kind="line",
        points=[(0, 0), (1, 0)],
        semantic_role="front_boundary",
    )
    service = SiteModelService()
    result = SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    service.apply_artist_override(result.geometry_ids[0], "driveway")
    presenter = SiteViewerPresenter(service)
    presenter.set_annotation_source_visible(AnnotationSource.AI_INFERRED, False)
    records = presenter.snapshot().records
    assert len(records) == 1
    assert records[0].annotation_source is AnnotationSource.ARTIST_OVERRIDE
