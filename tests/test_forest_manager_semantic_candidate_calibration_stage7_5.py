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
            "clurough": 0.0, "clunoise": 0.0, "cluedge": 0.0, "drotation": 0.0,
            "divers": 0, "distrefrandpos": True, "distpathrandpos": 0.0,
            "applytranslation": False, "applyrotation": False, "applyscale": False,
        }
    def list_forests(self, *, preflight=True): return ("FM_Forest_001",)
    def selected_forest_name(self, *, preflight=True): return "FM_Forest_001"
    def scene_units(self, *, preflight=True): return FakeUnits()
    def inventory(self, forest_name, *, preflight=True):
        props=[]
        for name,value in self.values.items():
            is_bool=isinstance(value,bool)
            writable=name not in {"distrefrandpos","applytranslation","applyrotation","applyscale"}
            props.append({"name":name,"value_class":"Boolean" if is_bool else ("Integer" if isinstance(value,int) else "Float"),"write_mode":"scalar" if writable else "read_only","readable":True,"value":value})
        return {"properties":props}


class FakeTx:
    def __init__(self, service): self.calls=[]; self.service=service


def make_controller():
    service=FakeService(); tx=FakeTx(service); controller=ForestManagerUIController(service, tx); controller.refresh_scene(); return controller


def test_naturalness_candidate_uses_only_writable_runtime_properties():
    plan=SemanticCalibrationPlanner(make_controller()).plan("naturalness","Natural")
    names={op.property_name for op in plan.operations}
    assert names == {"clurough","clunoise","cluedge","drotation","divers","distpathrandpos"}
    assert "distrefrandpos" not in names
    assert plan.executable is True


def test_naturalness_candidate_is_multi_parameter_semantic_plan():
    plan=SemanticCalibrationPlanner(make_controller()).plan("naturalness","Natural")
    values={op.property_name:op.value for op in plan.operations}
    assert values["clurough"] == 15.0
    assert values["clunoise"] == 20.0
    assert values["drotation"] == 30.0
    assert len(plan.operations) == 6


def test_variation_is_blocked_when_activation_flags_are_read_only_and_false():
    plan=SemanticCalibrationPlanner(make_controller()).plan("variation","High")
    assert plan.executable is False
    assert "applytranslation:read_only" in plan.blocked_reasons
    assert "applyrotation:read_only" in plan.blocked_reasons
    assert "applyscale:read_only" in plan.blocked_reasons
