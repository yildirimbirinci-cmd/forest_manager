from forest_manager.site_model import GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def test_ai_reason_and_evidence_survive_snapshot_restore():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "g1", GeometryKind.REGION, [(0, 0), (10, 0), (10, 10)], closed=True,
        metadata={"source_layer": "LAWN", "project_source_kind": "cad"},
    ))
    SemanticClassificationPipeline().analyze(service)
    original = service.resolved_annotation("g1")
    assert original.role is SemanticRole.LAWN
    assert original.reason == "source_metadata_match"
    restored = SiteModelService()
    restored.restore(type(service.snapshot()).from_dict(service.snapshot().to_dict()))
    annotation = restored.resolved_annotation("g1")
    assert annotation.reason == original.reason
    assert annotation.evidence == original.evidence
    assert annotation.confidence == original.confidence
