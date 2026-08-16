from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SiteModelService,
    SiteViewerPresenter,
)


def _service():
    service = SiteModelService()
    ingestor = SiteModelIngestor()
    for source_id in ("site-a", "site-b"):
        source = ProjectSource(source_id, ProjectSourceKind.CAD, f"{source_id}.dxf")
        entity = ImportedEntity.create(
            source_id=source_id,
            entity_id="E1",
            kind="line",
            points=[(0, 0), (10, 0)],
            semantic_role="street_edge",
            semantic_confidence=0.8,
        )
        ingestor.ingest(service, ImportBatch(source, (entity,)))
    return service


def test_presenter_switches_project_sources_and_limits_visible_geometry():
    presenter = SiteViewerPresenter(_service())
    assert presenter.snapshot().source_ids == ("site-a", "site-b")
    state = presenter.set_active_source("site-b")
    assert state.active_source_id == "site-b"
    assert state.geometry_count == 1
    assert {record.source_id for record in presenter.snapshot().records} == {"site-b"}


def test_source_switch_clears_selection_that_is_not_visible():
    presenter = SiteViewerPresenter(_service())
    presenter.select("cad:site-a:E1")
    state = presenter.set_active_source("site-b")
    assert state.selected_geometry_ids == ()
    assert state.active_geometry_id is None
