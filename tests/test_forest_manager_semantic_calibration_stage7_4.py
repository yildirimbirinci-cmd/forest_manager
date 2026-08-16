from __future__ import annotations

from dataclasses import dataclass

from forest_manager.ui.controller import ForestManagerUIController


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
        self.forests = ("FM_Forest_001",)
        self.selected = "FM_Forest_001"
        self.values = {
            "units_x": 7500.0,
            "units_y": 7500.0,
            "lock_ratio": True,
            "clurough": 0.5,
            "clunoise": 0.25,
            "cluedge": 0.1,
            "drotation": 15.0,
            "applyrotation": True,
            "zrotmin": -45.0,
            "zrotmax": 45.0,
            "applyscale": True,
            "scalexmin": 80.0,
            "scalexmax": 120.0,
            "scaleymin": 80.0,
            "scaleymax": 120.0,
            "scalezmin": 90.0,
            "scalezmax": 110.0,
        }

    def list_forests(self, *, preflight: bool = True):
        return self.forests

    def scene_units(self, *, preflight: bool = True):
        return FakeUnits()

    def selected_forest_name(self, *, preflight: bool = True):
        return self.selected

    def inventory(self, forest_name: str, *, preflight: bool = True):
        bools = {"lock_ratio", "applyrotation", "applyscale"}
        properties = []
        for name, value in self.values.items():
            properties.append(
                {
                    "name": name,
                    "value_class": "Boolean" if name in bools else "Float",
                    "write_mode": "scalar",
                    "readable": True,
                    "value": value,
                }
            )
        return {"forest_name": forest_name, "property_count": len(properties), "properties": properties}


@dataclass(frozen=True)
class FakeResult:
    operation_count: int
    write_verified: bool = True


class FakeTransactionManager:
    def __init__(self, service: FakeService) -> None:
        self.service = service
        self.calls = []

    def execute(self, operations, *, default_forest_name=None, rollback_on_success=False):
        operations = tuple(operations)
        self.calls.append((operations, default_forest_name, rollback_on_success))
        for operation in operations:
            self.service.values[operation.property_name] = operation.value
        return FakeResult(len(operations))


def make_controller():
    service = FakeService()
    transaction = FakeTransactionManager(service)
    controller = ForestManagerUIController(service, transaction)
    controller.refresh_scene()
    return controller, service, transaction


def test_spacing_uses_active_display_units_instead_of_raw_system_units():
    controller, _, _ = make_controller()
    controls = {item.key: item for item in controller.state.artist_controls}
    assert controls["density_spacing"].value == 75.0
    assert controls["density_spacing"].display_suffix == "m"


def test_spacing_converts_display_meters_back_to_system_units_for_transaction():
    controller, _, transaction = make_controller()
    state = controller.set_artist_control("density_spacing", 60.0)
    pending = {edit.property_name: edit.value for edit in state.pending_edits}
    assert pending == {"units_x": 6000.0, "units_y": 6000.0}
    controller.apply_pending()
    assert len(transaction.calls) == 1


def test_semantic_calibration_snapshot_is_read_only_and_uses_real_values():
    controller, service, transaction = make_controller()
    before = dict(service.values)
    snapshot = controller.semantic_calibration_snapshot()
    naturalness = snapshot["controls"]["naturalness"]
    values = {item["name"]: item["value"] for item in naturalness["available_properties"]}
    assert snapshot["read_only"] is True
    assert values["clurough"] == 0.5
    assert values["clunoise"] == 0.25
    assert values["drotation"] == 15.0
    assert service.values == before
    assert transaction.calls == []


def test_variation_probe_reports_available_write_contract_without_writing():
    controller, service, transaction = make_controller()
    before = dict(service.values)
    snapshot = controller.semantic_calibration_snapshot()
    properties = snapshot["controls"]["variation"]["available_properties"]
    names = {item["name"] for item in properties}
    assert {"applyrotation", "zrotmin", "zrotmax", "applyscale", "scalexmin", "scalexmax", "scalezmin", "scalezmax"} <= names
    assert all(item["writable"] for item in properties)
    assert service.values == before
    assert transaction.calls == []


def test_compact_distance_format_removes_redundant_zeroes():
    from forest_manager.ui.main_window import _trim_localized_decimal

    assert _trim_localized_decimal("75,000", ",") == "75"
    assert _trim_localized_decimal("75,500", ",") == "75,5"
    assert _trim_localized_decimal("75.250", ".") == "75.25"
