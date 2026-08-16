from __future__ import annotations

from dataclasses import dataclass

from forest_manager.forest_control.service import ForestControlError
from forest_manager.ui.controller import ForestManagerUIController
from forest_manager.ui.semantic_controls import artist_control_specs


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
            "clunoise": 0.5,
            "drotation": 0.5,
            "seed": 123456,
        }

    def list_forests(self, *, preflight: bool = True):
        return self.forests

    def scene_units(self, *, preflight: bool = True):
        return FakeUnits()

    def selected_forest_name(self, *, preflight: bool = True):
        return self.selected

    def inventory(self, forest_name: str, *, preflight: bool = True):
        if forest_name not in self.forests:
            raise ForestControlError("missing forest")
        classes = {
            "units_x": "Float", "units_y": "Float", "lock_ratio": "Boolean",
            "clurough": "Float", "clunoise": "Float", "drotation": "Float", "seed": "Integer",
        }
        props = [
            {"name": name, "value_class": classes[name], "write_mode": "scalar", "readable": True, "value": value}
            for name, value in self.values.items()
        ]
        return {"forest_name": forest_name, "property_count": len(props), "properties": props}


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
    tx = FakeTransactionManager(service)
    controller = ForestManagerUIController(service, tx)
    controller.refresh_scene()
    return controller, service, tx


def test_artist_control_catalog_is_intent_driven_not_raw_property_mirroring():
    specs = {spec.key: spec for spec in artist_control_specs()}
    assert set(specs) == {
        "density_spacing", "naturalness", "cluster_character", "variation",
        "species_diversity", "boundary_behavior", "height_character", "ground_visibility",
    }
    assert specs["naturalness"].dependent_properties == (
        "clurough", "clunoise", "cluedge", "drotation", "divers", "distrefrandpos", "distpathrandpos"
    )
    assert specs["variation"].direct_write is False


def test_density_spacing_reads_existing_synchronized_value():
    controller, _, _ = make_controller()
    states = {item.key: item for item in controller.state.artist_controls}
    assert states["density_spacing"].value == 75.0
    assert states["density_spacing"].available is True
    assert set(states["density_spacing"].affected_properties) == {"units_x", "units_y", "lock_ratio"}


def test_density_spacing_updates_x_and_y_as_one_artist_control():
    controller, _, _ = make_controller()
    state = controller.set_artist_control("density_spacing", 60.0)
    pending = {edit.property_name: edit.value for edit in state.pending_edits}
    assert pending == {"units_x": 6000.0, "units_y": 6000.0}
    assert state.error is None
    assert state.status == "Plant Spacing: 60 m"


def test_density_spacing_apply_uses_one_atomic_transaction_for_both_raw_properties():
    controller, service, tx = make_controller()
    controller.set_artist_control("density_spacing", 60.0)
    state = controller.apply_pending()
    assert len(tx.calls) == 1
    operations, forest_name, rollback_on_success = tx.calls[0]
    assert forest_name == "FM_Forest_001"
    assert rollback_on_success is False
    assert [(op.property_name, op.value) for op in operations] == [("units_x", 6000.0), ("units_y", 6000.0)]
    assert service.values["units_x"] == 6000.0
    assert service.values["units_y"] == 6000.0
    assert state.pending_edits == ()


def test_naturalness_is_now_calibrated_and_produces_pending_raw_changes():
    controller, _, tx = make_controller()
    state = controller.set_artist_control("naturalness", "Wild")
    values = {item.key: item.value for item in state.artist_controls}
    assert values["naturalness"] == "Wild"
    assert {edit.property_name for edit in state.pending_edits} == {"clurough", "clunoise", "drotation"}
    assert tx.calls == []


def test_invalid_artist_choice_is_rejected():
    controller, _, _ = make_controller()
    state = controller.set_artist_control("naturalness", "Impossible")
    assert state.status == "Artist control rejected"
    assert state.error is not None


def test_artist_controls_report_only_properties_available_on_selected_forest():
    controller, _, _ = make_controller()
    states = {item.key: item for item in controller.state.artist_controls}
    assert set(states["naturalness"].affected_properties) == {"clurough", "clunoise", "drotation"}
    assert states["boundary_behavior"].available is False
