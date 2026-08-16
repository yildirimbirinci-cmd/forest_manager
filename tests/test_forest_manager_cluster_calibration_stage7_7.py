from __future__ import annotations

from dataclasses import dataclass

from forest_manager.ui.controller import ForestManagerUIController
from forest_manager.ui.semantic_controls import calibration_probe_keys


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
            "clusize": 0.0,
            "clurough": 0.0,
            "clunoise": 0.0,
            "cluedge": 0.0,
            "problist": [100.0, 75.0, 50.0],
        }

    def list_forests(self, *, preflight=True):
        return ("FM_Forest_001",)

    def selected_forest_name(self, *, preflight=True):
        return "FM_Forest_001"

    def scene_units(self, *, preflight=True):
        return FakeUnits()

    def inventory(self, forest_name, *, preflight=True):
        props = []
        for name, value in self.values.items():
            if name == "problist":
                value_class = "Array"
                write_mode = "array_scalar"
            else:
                value_class = "Float"
                write_mode = "scalar"
            props.append({
                "name": name,
                "value_class": value_class,
                "write_mode": write_mode,
                "readable": True,
                "value": value,
            })
        return {"forest_name": forest_name, "properties": props}


class FakeTx:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, operations, **kwargs):
        self.calls.append((tuple(operations), kwargs))
        raise AssertionError("Stage 7.7 calibration probe must not write")


def test_cluster_character_is_in_calibration_probe_contract():
    assert "cluster_character" in calibration_probe_keys()


def test_cluster_character_snapshot_uses_runtime_values_without_writing():
    service = FakeService()
    tx = FakeTx()
    controller = ForestManagerUIController(service, tx)
    controller.refresh_scene()
    before = dict(service.values)

    snapshot = controller.semantic_calibration_snapshot()
    cluster = snapshot["controls"]["cluster_character"]
    values = {item["name"]: item["value"] for item in cluster["available_properties"]}

    assert snapshot["read_only"] is True
    assert values["clusize"] == 0.0
    assert values["clurough"] == 0.0
    assert values["clunoise"] == 0.0
    assert values["cluedge"] == 0.0
    assert values["problist"] == [100.0, 75.0, 50.0]
    assert service.values == before
    assert tx.calls == []


def test_cluster_character_reports_scalar_and_array_write_contracts():
    service = FakeService()
    controller = ForestManagerUIController(service, FakeTx())
    controller.refresh_scene()
    rows = controller.semantic_calibration_snapshot()["controls"]["cluster_character"]["available_properties"]
    by_name = {item["name"]: item for item in rows}
    assert by_name["clusize"]["write_mode"] == "scalar"
    assert by_name["problist"]["write_mode"] == "array_scalar"
