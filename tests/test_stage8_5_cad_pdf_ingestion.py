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


def test_cad_entity_maps_to_stable_site_geometry_with_source_provenance():
    source = ProjectSource("site-main", ProjectSourceKind.CAD, r"plans/site.dxf")
    entity = ImportedEntity.create(
        source_id="site-main",
        entity_id="7A",
        kind="polyline",
        points=[(0, 0), (12, 0), (12, 4)],
        closed=False,
        layer="BOUNDARY",
        semantic_role=SemanticRole.FRONT_BOUNDARY,
        semantic_confidence=0.91,
    )
    service = SiteModelService()
    result = SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))

    assert result.geometry_ids == ("cad:site-main:7A",)
    geometry = service.geometry("cad:site-main:7A")
    assert geometry.metadata["source_layer"] == "BOUNDARY"
    assert geometry.metadata["source_entity_id"] == "7A"
    assert geometry.source_ref == "plans/site.dxf#entity=7A&layer=BOUNDARY"
    resolved = service.resolved_annotation(geometry.geometry_id)
    assert resolved.role is SemanticRole.FRONT_BOUNDARY
    assert resolved.source.value == "ai_inferred"
    assert resolved.confidence == 0.91


def test_pdf_entity_preserves_page_identity():
    source = ProjectSource("landscape-pdf", ProjectSourceKind.PDF, "plans/landscape.pdf", page_count=3)
    entity = ImportedEntity.create(
        source_id="landscape-pdf",
        entity_id="path-42",
        kind="region",
        points=[(1, 1), (4, 1), (4, 4)],
        closed=True,
        page_index=1,
        semantic_role="planting_bed",
    )
    service = SiteModelService()
    SiteModelIngestor().ingest(service, ImportBatch(source, (entity,)))

    geometry = service.geometry("pdf:landscape-pdf:p1:path-42")
    assert geometry.metadata["source_page_index"] == 1
    assert geometry.source_ref.endswith("#entity=path-42&page=1")
