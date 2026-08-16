from __future__ import annotations

from dataclasses import dataclass

from forest_manager.devtools.acceptance.forest_manager_boundary_behavior_probe_stage7_10 import build_probe


@dataclass(frozen=True)
class FakeUnits:
    display_type: str = "metric"
    display_unit: str = "meters"
    system_type: str = "centimeters"
    system_scale: float = 1.0
    one_meter_system_units: float = 100.0
    one_centimeter_system_units: float = 1.0
    one_millimeter_system_units: float = 0.1
    sample_one_meter_display: str = "1.0m"
    custom_name: str = ""
    custom_value: float = 0.0
    custom_unit: str = ""


class FakeService:
    def selected_forest_name(self):
        return "FM_Forest_001"

    def scene_units(self, *, preflight=False):
        return FakeUnits()

    def inventory(self, forest_name, *, preflight=False):
        assert forest_name == "FM_Forest_001"
        return {
            "properties": [
                {"name": "threshold", "value": 10.0, "value_class": "Float", "write_mode": "scalar", "readable": True, "array_metadata": None},
                {"name": "spdensinc", "value": 25.0, "value_class": "Float", "write_mode": "scalar", "readable": True, "array_metadata": None},
                {"name": "arwidthlist", "value": None, "value_class": "ArrayParameter", "write_mode": "read_only", "readable": True, "array_metadata": {"count": 2}},
                {"name": "spdenscurve", "value": None, "value_class": "CurveClass", "write_mode": "read_only", "readable": True, "array_metadata": None},
            ]
        }


def test_probe_is_read_only_and_groups_boundary_candidates():
    payload = build_probe(FakeService())
    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert payload["verified"] is True
    boundary = payload["boundary_behavior"]
    assert "threshold" in boundary["writable_scalar_candidates"]
    assert "spdensinc" in boundary["writable_scalar_candidates"]
    assert "arwidthlist" in boundary["adapter_required_candidates"]
    assert "spdenscurve" in boundary["read_only_or_opaque_candidates"]


def test_probe_never_requests_write_service_methods():
    service = FakeService()
    payload = build_probe(service)
    assert payload["policy"]["synchronized_area_arrays_not_mutated"] is True
    assert payload["policy"]["opaque_falloff_curves_not_mutated"] is True


def test_scene_units_are_preserved_for_future_distance_calibration():
    payload = build_probe(FakeService())
    assert payload["scene_units"]["display_unit"] == "meters"
    assert payload["scene_units"]["one_meter_system_units"] == 100.0
