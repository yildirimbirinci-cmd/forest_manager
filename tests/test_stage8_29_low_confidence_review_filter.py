from forest_manager.site_model import (
    ImportBatch, ImportedEntity, ProjectSource, ProjectSourceKind,
    SiteModelIngestor, SiteModelService, SiteViewerPresenter,
)


def _presenter():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    entities = (
        ImportedEntity.create(source_id="site", entity_id="LOW", kind="line", points=[(0,0),(1,0)], semantic_role="street_edge", semantic_confidence=0.25),
        ImportedEntity.create(source_id="site", entity_id="HIGH", kind="line", points=[(0,1),(1,1)], semantic_role="sidewalk", semantic_confidence=0.85),
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, entities))
    return SiteViewerPresenter(service)


def test_low_confidence_review_filters_to_ai_predictions_at_or_below_threshold():
    presenter = _presenter()
    state = presenter.set_low_confidence_review(True, threshold=0.5)
    assert state.low_confidence_review_enabled is True
    assert state.review_geometry_count == 1
    assert [r.geometry_id for r in presenter.snapshot().records] == ["cad:site:LOW"]
