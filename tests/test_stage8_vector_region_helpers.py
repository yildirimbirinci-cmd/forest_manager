from forest_manager.forest_control.vector_region_helpers import _helper_specs


def test_helper_specs_are_deterministic_and_role_named():
    zones={
        "verified": True,
        "node_name": "Line001",
        "wall_band": {"parts": [{"points_world_xy": [{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":1}]}]},
        "walkway_band": {"parts": [
            {"points_world_xy": [{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":1}]},
            {"points_world_xy": [{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":1}]},
        ]},
        "interior": {"parts": [{"points_world_xy": [{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":1}]}]},
    }
    specs=_helper_specs(zones)
    assert [s["name"] for s in specs] == [
        "FM_Region_Line001_Wall_001",
        "FM_Region_Line001_Walkway_001",
        "FM_Region_Line001_Walkway_002",
        "FM_Region_Line001_Interior_001",
    ]
    assert [s["role"] for s in specs] == ["wall_band","walkway_band","walkway_band","interior"]
