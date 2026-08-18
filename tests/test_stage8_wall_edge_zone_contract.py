from __future__ import annotations

import inspect
from forest_manager.forest_control.wall_edge_zone_plan import build_wall_edge_zone_plan


def test_zone_plan_is_artist_edge_driven_and_raster_free():
    source = inspect.getsource(build_wall_edge_zone_plan)
    assert "annotation.wall_segments" in source
    assert '"walkway_open_edge"' in source
    assert '"distribution_map_used": False' in source
    assert '"reference_image_coordinates_used": False' in source
    assert '"forest_pack_mutated": False' in source
