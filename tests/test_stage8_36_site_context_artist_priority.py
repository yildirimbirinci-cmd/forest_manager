from forest_manager.site_model import AnnotationSource, GeometryKind, SemanticClassificationPipeline, SemanticRole, SiteModelService, create_geometry


def test_context_reanalysis_never_overwrites_artist_boundary_override():
    service = SiteModelService()
    service.upsert_geometry(create_geometry("street", GeometryKind.LINE, [(0, 0), (100, 0)]))
    service.upsert_geometry(create_geometry("edge", GeometryKind.POLYLINE, [(0, 5), (100, 5)]))
    service.apply_artist_confirmation("street", SemanticRole.STREET_EDGE)
    service.apply_artist_override("edge", SemanticRole.KEEP_CLEAR)

    SemanticClassificationPipeline().analyze(service)

    resolved = service.resolved_annotation("edge")
    assert resolved.role is SemanticRole.KEEP_CLEAR
    assert resolved.source is AnnotationSource.ARTIST_OVERRIDE
    ai = [a for a in service.annotations_for("edge") if a.source is AnnotationSource.AI_INFERRED][-1]
    assert ai.reason.startswith("site_context_")
    assert ai.source is AnnotationSource.AI_INFERRED
