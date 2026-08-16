from __future__ import annotations

from forest_manager.site_model import SemanticRole, SiteModelService, create_geometry


def make_service() -> SiteModelService:
    service = SiteModelService()
    service.upsert_geometry(create_geometry("g1", "polyline", [(0, 0), (10, 0)]))
    return service


def test_ai_is_primary_until_artist_confirms_or_overrides():
    service = make_service()
    service.apply_ai_annotation("g1", SemanticRole.FRONT_BOUNDARY, confidence=0.84)
    assert service.resolved_annotation("g1").role is SemanticRole.FRONT_BOUNDARY
    assert service.resolved_annotation("g1").artist_confirmed is False


def test_artist_override_has_higher_priority_than_newer_ai_reanalysis():
    service = make_service()
    service.apply_ai_annotation("g1", SemanticRole.FRONT_BOUNDARY, confidence=0.8)
    service.apply_artist_override("g1", SemanticRole.SIDE_BOUNDARY, notes="artist correction")
    service.apply_ai_annotation("g1", SemanticRole.REAR_BOUNDARY, confidence=0.99)
    resolved = service.resolved_annotation("g1")
    assert resolved.role is SemanticRole.SIDE_BOUNDARY
    assert resolved.artist_confirmed is True
    assert resolved.source.value == "artist_override"


def test_artist_confirmation_can_confirm_current_ai_role_without_retyping_it():
    service = make_service()
    service.apply_ai_annotation("g1", SemanticRole.FRONT_BOUNDARY, confidence=0.95)
    confirmed = service.apply_artist_confirmation("g1")
    assert confirmed.role is SemanticRole.FRONT_BOUNDARY
    assert service.resolved_annotation("g1").source.value == "artist_confirmed"
