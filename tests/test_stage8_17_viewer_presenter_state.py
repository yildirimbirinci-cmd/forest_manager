from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SemanticRole,
    SiteModelIngestor,
    SiteModelService,
    SiteViewerPresenter,
)


def _presenter():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entity = ImportedEntity.create(
        source_id="site",
        entity_id="E1",
        kind="line",
        points=[(0, 0), (10, 0)],
        semantic_role="street_edge",
        semantic_confidence=0.82,
        label="AI frontage",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    return SiteViewerPresenter(service)


def test_presenter_reports_active_semantic_state_after_selection():
    presenter = _presenter()
    state = presenter.select("cad:site:E1")
    assert state.selected_geometry_ids == ("cad:site:E1",)
    assert state.active_geometry_id == "cad:site:E1"
    assert state.active_role is SemanticRole.STREET_EDGE
    assert state.active_source.value == "ai_inferred"
    assert state.active_confidence == 0.82
    assert state.active_label == "AI frontage"
