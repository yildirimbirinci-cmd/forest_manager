from __future__ import annotations

from dataclasses import dataclass

from forest_manager.ui.controller import ForestManagerUIController
from forest_manager.ui.semantic_calibration import SemanticCalibrationPlanner


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
    def __init__(self) -> None:
        self.values = {
            "clusize": 2000.0,
            "clurough": 0.0,
            "clunoise": 0.0,
            "cluedge": 0.0,
            "problist": [100.0, 75.0, 50.0],
        }

    def list_forests(self, *, preflight=True): return ("FM_Forest_001",)
    def selected_forest_name(self, *, preflight=True): return "FM_Forest_001"
    def scene_units(self, *, preflight=True): return FakeUnits()

    def inventory(self, forest_name, *, preflight=True):
        props = []
        for name, value in self.values.items():
            if name == "problist":
                props.append({"name": name, "value_class": "ArrayParameter", "write_mode": "read_only", "readable": True, "value": None})
            else:
                props.append({"name": name, "value_class": "Float", "write_mode": "scalar", "readable": True, "value": value})
        return {"properties": props}


class FakeTx:
    def __init__(self): self.calls = []


def make_controller():
    controller = ForestManagerUIController(FakeService(), FakeTx())
    controller.refresh_scene()
    return controller


def test_small_groups_uses_four_writable_cluster_scalars_only():
    plan = SemanticCalibrationPlanner(make_controller()).plan("cluster_character", "Small Groups")
    names = {op.property_name for op in plan.operations}
    assert names == {"clusize", "clurough", "clunoise", "cluedge"}
    assert "problist" not in names
    assert plan.executable is True


def test_cluster_size_is_converted_from_display_meters_to_system_units():
    plan = SemanticCalibrationPlanner(make_controller()).plan("cluster_character", "Small Groups")
    values = {op.property_name: op.value for op in plan.operations}
    assert values["clusize"] == 1000.0
    assert values["clurough"] == 10.0
    assert values["clunoise"] == 5.0
    assert values["cluedge"] == 10.0


def test_medium_and_large_profiles_increase_cluster_size():
    controller = make_controller()
    medium = SemanticCalibrationPlanner(controller).plan("cluster_character", "Medium Clusters")
    large = SemanticCalibrationPlanner(controller).plan("cluster_character", "Large Masses")
    medium_values = {op.property_name: op.value for op in medium.operations}
    large_values = {op.property_name: op.value for op in large.operations}
    assert medium_values["clusize"] == 2000.0
    assert large_values["clusize"] == 4000.0
    assert large_values["clusize"] > medium_values["clusize"]


def test_solitary_is_blocked_until_cluster_disable_capability_is_known():
    plan = SemanticCalibrationPlanner(make_controller()).plan("cluster_character", "Solitary")
    assert plan.executable is False
    assert "solitary_requires_cluster_disable_or_distribution_mode_capability" in plan.blocked_reasons
