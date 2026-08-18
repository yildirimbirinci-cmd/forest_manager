from __future__ import annotations

import inspect

from forest_manager.forest_control.wall_edge_zone_geometry import build_wall_edge_zone_geometry


def test_zone_geometry_contract_is_vector_only_and_fail_closed():
    source = inspect.getsource(build_wall_edge_zone_geometry)
    assert "distribution_map_used" in source
    assert '"distribution_map_used": False' in source
    assert '"reference_image_coordinates_used": False' in source
    assert '"forest_pack_mutated": False' in source
    assert "convex" in source.lower()
