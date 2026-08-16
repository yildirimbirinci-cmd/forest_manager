from __future__ import annotations

from forest_manager.site_model import BOUNDARY_ROLES, SemanticRole, is_boundary_role


def test_boundary_role_mapping_separates_context_edges_from_area_zones():
    assert SemanticRole.FRONT_BOUNDARY in BOUNDARY_ROLES
    assert SemanticRole.REAR_BOUNDARY in BOUNDARY_ROLES
    assert SemanticRole.SIDE_BOUNDARY in BOUNDARY_ROLES
    assert SemanticRole.BUILDING_EDGE in BOUNDARY_ROLES
    assert SemanticRole.WALL in BOUNDARY_ROLES
    assert is_boundary_role("street_edge") is True
    assert is_boundary_role("planting_bed") is False
    assert is_boundary_role("species_zone") is False
