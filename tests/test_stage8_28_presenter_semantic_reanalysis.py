from pathlib import Path

from forest_manager.site_model import GeometryKind, SemanticRole, SiteModelService, SiteViewerPresenter, create_geometry


def test_presenter_can_reanalyze_visible_geometry_without_overwriting_artist_override(tmp_path: Path):
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "g1", GeometryKind.POLYLINE, [(0, 0), (10, 0)],
        metadata={"source_layer": "SIDEWALK", "project_source_kind": "cad", "project_source_id": "site"},
    ))
    service.apply_artist_override("g1", SemanticRole.KEEP_CLEAR)
    presenter = SiteViewerPresenter(service, persistence_path=tmp_path / "site.json")
    state, result = presenter.reanalyze_semantics()
    assert result.classified_geometry_ids == ("g1",)
    assert state.geometry_count == 1
    assert service.resolved_annotation("g1").role is SemanticRole.KEEP_CLEAR
    ai = [item for item in service.annotations_for("g1") if item.source.value == "ai_inferred"]
    assert ai[-1].role is SemanticRole.SIDEWALK
    assert ai[-1].reason == "source_metadata_match"
