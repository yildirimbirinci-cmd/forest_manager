from __future__ import annotations

from forest_manager.site_model import (
    GeometryKind,
    ImportedEntity,
    ImportBatch,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SiteModelService,
    SiteModelViewerBinding,
    SiteModelViewerInteraction,
)


def test_viewer_binding_filters_and_marks_selection():
    service = SiteModelService()
    source = ProjectSource("pdf-plan", ProjectSourceKind.PDF, "plan.pdf", page_count=2)
    batch = ImportBatch(
        source,
        (
            ImportedEntity.create(source_id="pdf-plan", entity_id="a", kind=GeometryKind.LINE, points=((0, 0), (10, 0)), page_index=0, layer="A"),
            ImportedEntity.create(source_id="pdf-plan", entity_id="b", kind=GeometryKind.POLYLINE, points=((20, 20), (30, 20), (30, 30)), page_index=1, layer="B"),
        ),
    )
    result = SiteModelIngestor().ingest(service, batch)
    interaction = SiteModelViewerInteraction(service)
    interaction.select((result.geometry_ids[1],))

    snapshot = SiteModelViewerBinding().build(service, interaction=interaction, page_index=1)

    assert len(snapshot.records) == 1
    assert snapshot.records[0].geometry_id == result.geometry_ids[1]
    assert snapshot.records[0].selected is True
    assert snapshot.records[0].active is True
    assert snapshot.bounds is not None
    assert (snapshot.bounds.min_x, snapshot.bounds.min_y, snapshot.bounds.max_x, snapshot.bounds.max_y) == (20.0, 20.0, 30.0, 30.0)
