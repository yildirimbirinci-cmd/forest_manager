from forest_manager.site_model import (
    AnnotationSource, ImportBatch, ImportedEntity, ProjectSource, ProjectSourceKind,
    SemanticRole, SiteModelIngestor, SiteModelService, SiteViewerPresenter,
)


def test_select_all_visible_and_batch_assign_role_updates_every_selected_geometry():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entities = tuple(
        ImportedEntity.create(source_id="site", entity_id=str(i), kind="line", points=[(0,i),(1,i)], semantic_role="street_edge", semantic_confidence=0.4)
        for i in range(3)
    )
    service = SiteModelService(); SiteModelIngestor().ingest(service, ImportBatch(source, entities))
    presenter = SiteViewerPresenter(service)
    state = presenter.select_all_visible()
    assert len(state.selected_geometry_ids) == 3
    presenter.assign_role(SemanticRole.PLANTING_BED)
    for geometry_id in state.selected_geometry_ids:
        annotation = service.resolved_annotation(geometry_id)
        assert annotation.role is SemanticRole.PLANTING_BED
        assert annotation.source is AnnotationSource.ARTIST_OVERRIDE
