from __future__ import annotations

from forest_manager.site_model import (
    ImportBatch,
    ImportedEntity,
    ProjectSource,
    ProjectSourceKind,
    SemanticRole,
    SiteModelIngestor,
    SiteModelService,
)


def test_reimport_updates_geometry_and_ai_without_overwriting_artist_correction():
    source = ProjectSource("site", ProjectSourceKind.CAD, "site.dxf")
    ingestor = SiteModelIngestor()
    service = SiteModelService()

    initial = ImportedEntity.create(
        source_id="site",
        entity_id="B1",
        kind="polyline",
        points=[(0, 0), (10, 0)],
        layer="EDGE",
        semantic_role="street_edge",
        semantic_confidence=0.70,
    )
    ingestor.ingest(service, ImportBatch(source, (initial,)))
    service.apply_artist_override("cad:site:B1", SemanticRole.FRONT_BOUNDARY, notes="artist verified frontage")

    revised = ImportedEntity.create(
        source_id="site",
        entity_id="B1",
        kind="polyline",
        points=[(0, 0), (12, 0)],
        layer="EDGE",
        semantic_role="side_boundary",
        semantic_confidence=0.99,
    )
    ingestor.ingest(service, ImportBatch(source, (revised,)))

    assert service.geometry("cad:site:B1").points[-1].x == 12.0
    resolved = service.resolved_annotation("cad:site:B1")
    assert resolved.role is SemanticRole.FRONT_BOUNDARY
    assert resolved.source.value == "artist_override"
    assert resolved.notes == "artist verified frontage"
