from __future__ import annotations

from forest_manager.forest_control.plant_group_execution import _get_single_forest_site_polygon


class FakeService:
    def single_forest_area_polygon(self, forest_name, *, sample_count, preflight):
        return {
            "forest_name": forest_name,
            "spline_name": "Line001",
            "spline_count": 1,
            "samples_per_spline": sample_count,
            "bounds_width_meters": 18.6107,
            "bounds_height_meters": 5.6073,
            "normalized_rings": [[
                [0.0, 1.0],
                [1.0, 1.0],
                [1.0, 0.0],
                [0.0, 0.0],
            ]],
            "coordinate_space": "normalized_bbox_with_pil_y_flip",
            "read_only": True,
            "verified": True,
        }


def test_bridge_0981_normalized_rings_are_adapted_to_scene_map_contract():
    result = _get_single_forest_site_polygon(
        "FM_Forest_001", sample_count=256, service=FakeService()
    )
    assert result["points_normalized"] == [
        [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]
    ]
    assert result["width_system"] == 18.6107
    assert result["height_system"] == 5.6073


def test_multiple_rings_fail_closed_for_single_boundary_execution():
    class MultiRing(FakeService):
        def single_forest_area_polygon(self, forest_name, *, sample_count, preflight):
            data = super().single_forest_area_polygon(
                forest_name, sample_count=sample_count, preflight=preflight
            )
            data["normalized_rings"] = [data["normalized_rings"][0], data["normalized_rings"][0]]
            return data

    try:
        _get_single_forest_site_polygon("FM_Forest_001", service=MultiRing())
    except Exception as exc:
        assert "exactly one normalized closed ring" in str(exc)
    else:
        raise AssertionError("multiple rings must fail closed")
