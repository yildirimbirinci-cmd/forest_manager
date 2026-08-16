from __future__ import annotations

import pytest

from forest_manager.site_model import GeometryKind, SemanticRole, SitePoint, create_geometry


def test_site_geometry_supports_stage8_import_shapes_and_metadata():
    geometry = create_geometry(
        "cad:polyline:17",
        GeometryKind.POLYLINE,
        [(0.0, 0.0), (4.0, 0.0), SitePoint(4.0, 3.0)],
        closed=True,
        source_ref="plan.dxf#17",
        metadata={"layer": "LANDSCAPE"},
    )
    assert geometry.geometry_id == "cad:polyline:17"
    assert geometry.kind is GeometryKind.POLYLINE
    assert geometry.closed is True
    assert geometry.points[-1].z == 0.0
    assert geometry.metadata["layer"] == "LANDSCAPE"


def test_region_geometry_rejects_invalid_point_count():
    with pytest.raises(ValueError, match="at least three"):
        create_geometry("pdf:region:1", GeometryKind.REGION, [(0.0, 0.0), (1.0, 0.0)])


def test_stage8_semantic_roles_cover_site_context_and_artist_zones():
    required = {
        "front_boundary", "rear_boundary", "side_boundary", "sidewalk", "street_edge",
        "driveway", "parking", "building_edge", "wall", "planting_bed", "lawn",
        "species_zone", "cluster_zone", "keep_clear",
    }
    assert required <= {role.value for role in SemanticRole}
