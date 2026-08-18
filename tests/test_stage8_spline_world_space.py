from __future__ import annotations
import forest_manager.forest_control.spline_world_space as module

def test_world_space_reader_parses_verified_closed_geometry(monkeypatch):
    monkeypatch.setattr(module, "ensure_current_bridge", lambda: None)
    monkeypatch.setattr(module, "send_command", lambda command: {
        "ok": True,
        "data": {
            "verified": True, "read_only": True, "coordinate_system": "world",
            "all_splines_closed": True, "node_name": "Line001", "node_class": "line",
            "spline_count": 1, "samples_per_spline": 8,
            "scene_units": {"one_meter_system_units": 100.0},
            "splines": [{
                "spline_index": 1, "closed": True, "knot_count": 3,
                "knots_world": [{"x":0,"y":0,"z":0},{"x":100,"y":0,"z":0},{"x":0,"y":100,"z":0}],
                "sample_count": 8,
                "samples_world": [{"x":i,"y":0,"z":0} for i in range(8)],
            }],
        },
    })
    result = module.read_selected_spline_world_space(samples_per_spline=8)
    assert result.node_name == "Line001"
    assert result.coordinate_system == "world"
    assert result.all_closed is True
    assert result.total_knot_count == 3
    assert len(result.splines[0].samples) == 8

def test_sample_count_is_bounded():
    for value in (0, 7, 513, 1000):
        try:
            module.read_selected_spline_world_space(samples_per_spline=value, preflight=False)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")
