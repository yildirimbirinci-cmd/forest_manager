from forest_manager.site_model import (
    ImportBatch, ImportedEntity, ProjectSource, ProjectSourceKind,
    SiteModelIngestor, SiteModelService, SiteViewerPresenter,
)


def test_multi_selection_reports_mixed_roles_and_supports_toggle():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entities = (
        ImportedEntity.create(source_id="site", entity_id="A", kind="line", points=[(0,0),(1,0)], semantic_role="street_edge", semantic_confidence=0.8),
        ImportedEntity.create(source_id="site", entity_id="B", kind="line", points=[(0,1),(1,1)], semantic_role="sidewalk", semantic_confidence=0.8),
    )
    service = SiteModelService(); SiteModelIngestor().ingest(service, ImportBatch(source, entities))
    presenter = SiteViewerPresenter(service)
    presenter.select("cad:site:A")
    state = presenter.select("cad:site:B", additive=True)
    assert state.selection_mixed_roles is True
    assert len(state.selection_roles) == 2
    state = presenter.select("cad:site:B", additive=True, toggle=True)
    assert state.selected_geometry_ids == ("cad:site:A",)
