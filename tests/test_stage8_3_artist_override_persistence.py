from __future__ import annotations

from forest_manager.site_model import SemanticRole, SiteModelService, create_geometry


def test_artist_override_survives_save_load_and_ai_reanalysis(tmp_path):
    path = tmp_path / "site_model.json"
    service = SiteModelService()
    service.upsert_geometry(create_geometry("pdf:line:2", "line", [(1, 1), (5, 1)], source_ref="plan.pdf#2"))
    service.apply_ai_annotation("pdf:line:2", SemanticRole.STREET_EDGE, confidence=0.72)
    service.apply_artist_override("pdf:line:2", SemanticRole.FRONT_BOUNDARY, label="Main frontage")
    service.save(path)

    restored = SiteModelService()
    restored.load(path)
    assert restored.resolved_annotation("pdf:line:2").role is SemanticRole.FRONT_BOUNDARY
    assert restored.resolved_annotation("pdf:line:2").artist_confirmed is True

    restored.reanalyze_ai([
        restored.annotations_for("pdf:line:2")[0].__class__(
            geometry_id="pdf:line:2",
            role=SemanticRole.SIDEWALK,
            source=restored.annotations_for("pdf:line:2")[0].source,
            confidence=0.98,
        )
    ])
    assert restored.resolved_annotation("pdf:line:2").role is SemanticRole.FRONT_BOUNDARY


def test_snapshot_roundtrip_preserves_geometry_source_and_artist_provenance(tmp_path):
    path = tmp_path / "site_model.json"
    service = SiteModelService()
    service.upsert_geometry(create_geometry("cad:hatch:9", "hatch", [(0, 0), (3, 0), (3, 3)], closed=True, source_ref="site.dxf#9"))
    service.apply_artist_override("cad:hatch:9", SemanticRole.PLANTING_BED, notes="verified bed")
    service.save(path)

    restored = SiteModelService()
    snapshot = restored.load(path)
    assert snapshot.geometries[0].source_ref == "site.dxf#9"
    assert restored.resolved_annotation("cad:hatch:9").source.value == "artist_override"
    assert restored.resolved_annotation("cad:hatch:9").notes == "verified bed"
