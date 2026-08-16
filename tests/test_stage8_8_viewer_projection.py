from __future__ import annotations

from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SemanticRole,
    SiteModelIngestor,
    SiteModelService,
    SiteModelViewerAdapter,
)


def test_viewer_projection_exposes_source_and_ai_annotation_state():
    source = ProjectSource("plan", ProjectSourceKind.PDF, "garden.pdf", page_count=1)
    entity = ImportedEntity.create(
        source_id="plan",
        entity_id="R2",
        kind="region",
        points=[(0, 0), (5, 0), (5, 3)],
        closed=True,
        page_index=0,
        semantic_role=SemanticRole.LAWN,
        semantic_confidence=0.88,
        label="Main lawn",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))

    record = SiteModelViewerAdapter().build(service).by_geometry_id("pdf:plan:p0:R2")
    assert record.source_kind == "pdf"
    assert record.page_index == 0
    assert record.role is SemanticRole.LAWN
    assert record.annotation_source.value == "ai_inferred"
    assert record.artist_confirmed is False
    assert record.label == "Main lawn"


def test_viewer_projection_visibly_distinguishes_artist_override():
    source = ProjectSource("plan", ProjectSourceKind.CAD, "garden.dxf")
    entity = ImportedEntity.create(
        source_id="plan",
        entity_id="L7",
        kind="line",
        points=[(0, 0), (8, 0)],
        semantic_role="street_edge",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))
    service.apply_artist_override("cad:plan:L7", SemanticRole.FRONT_BOUNDARY, label="Front edge")

    record = SiteModelViewerAdapter().build(service).by_geometry_id("cad:plan:L7")
    assert record.role is SemanticRole.FRONT_BOUNDARY
    assert record.annotation_source.value == "artist_override"
    assert record.artist_confirmed is True
