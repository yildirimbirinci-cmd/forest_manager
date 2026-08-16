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


def _presenter(tmp_path):
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entity = ImportedEntity.create(
        source_id="site",
        entity_id="E1",
        kind="line",
        points=[(0, 0), (10, 0)],
        semantic_role="street_edge",
        semantic_confidence=0.8,
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    return service, SiteViewerPresenter(service, persistence_path=tmp_path / "site-model.json")


def test_presenter_assign_role_is_artist_override_and_persists(tmp_path):
    service, presenter = _presenter(tmp_path)
    presenter.select("cad:site:E1")
    state = presenter.assign_role(SemanticRole.FRONT_BOUNDARY)
    assert state.active_role is SemanticRole.FRONT_BOUNDARY
    assert state.active_source.value == "artist_override"

    restored = SiteModelService()
    restored.load(tmp_path / "site-model.json")
    resolved = restored.resolved_annotation("cad:site:E1")
    assert resolved is not None
    assert resolved.role is SemanticRole.FRONT_BOUNDARY
    assert resolved.source.value == "artist_override"


def test_presenter_approve_same_ai_role_is_artist_confirmed(tmp_path):
    _service, presenter = _presenter(tmp_path)
    presenter.select("cad:site:E1")
    state = presenter.approve()
    assert state.active_role is SemanticRole.STREET_EDGE
    assert state.active_source.value == "artist_confirmed"
