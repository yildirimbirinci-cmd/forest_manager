from __future__ import annotations

from dataclasses import dataclass

from forest_manager.forest_control.service import ForestControlError
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
            "seed": 123456,
            "mirror": False,
            "iconSize": 100.0,
            "tintcolor1": [219.3, 119.85, 0.0],
            "distmap": None,
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
        return {
            "forest_name": forest_name,
            "property_count": 5,
            "properties": [
                {"name": "seed", "value_class": "Integer", "write_mode": "scalar", "readable": True, "value": self.values["seed"]},
                {"name": "mirror", "value_class": "Boolean", "write_mode": "scalar", "readable": True, "value": self.values["mirror"]},
                {"name": "iconSize", "value_class": "Float", "write_mode": "scalar", "readable": True, "value": self.values["iconSize"]},
                {"name": "tintcolor1", "value_class": "Color", "write_mode": "color", "readable": True, "value": self.values["tintcolor1"]},
                {"name": "distmap", "value_class": "Bitmaptexture", "write_mode": "read_only", "readable": True, "value": self.values["distmap"]},
            ],
        }


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


def test_semantic_domain_mapping_and_editor_modes():
    controller, _, _ = make_controller()
    by_name = {row.name: row for row in controller.state.properties}
    assert by_name["seed"].domain == "Distribution"
    assert by_name["mirror"].domain == "Transform"
    assert by_name["iconSize"].domain == "Display / Render / Effects"
    assert by_name["tintcolor1"].domain == "Material / Animation"
    assert by_name["seed"].editor_kind == "int"
    assert by_name["mirror"].editor_kind == "bool"
    assert by_name["iconSize"].editor_kind == "float"
    assert by_name["tintcolor1"].editor_kind == "color"
    assert by_name["distmap"].writable is False


def test_pending_edit_tracks_dirty_state_and_revert_clears_it():
    controller, _, _ = make_controller()
    state = controller.set_pending_value("seed", "123457")
    assert len(state.pending_edits) == 1
    assert state.pending_edits[0].value == 123457
    state = controller.revert_pending()
    assert state.pending_edits == ()


def test_bool_float_and_color_editor_parsing():
    controller, _, _ = make_controller()
    controller.set_pending_value("mirror", "true")
    controller.set_pending_value("iconSize", "101,5")
    state = controller.set_pending_value("tintcolor1", "220.3, 119.85, 0")
    pending = {edit.property_name: edit.value for edit in state.pending_edits}
    assert pending["mirror"] is True
    assert pending["iconSize"] == 101.5
    assert pending["tintcolor1"] == [220.3, 119.85, 0.0]


def test_read_only_property_edit_is_rejected_without_dirty_state():
    controller, _, _ = make_controller()
    state = controller.set_pending_value("distmap", "anything")
    assert state.pending_edits == ()
    assert state.status == "Property edit rejected"
    assert "read-only" in str(state.error)


def test_apply_uses_unified_transaction_and_refreshes_inventory():
    controller, service, tx = make_controller()
    controller.set_pending_value("seed", 123457)
    controller.set_pending_value("mirror", True)
    state = controller.apply_pending()
    assert len(tx.calls) == 1
    operations, forest_name, rollback_on_success = tx.calls[0]
    assert forest_name == "FM_Forest_001"
    assert rollback_on_success is False
    assert [(op.property_name, op.value) for op in operations] == [("seed", 123457), ("mirror", True)]
    assert service.values["seed"] == 123457
    assert service.values["mirror"] is True
    assert state.pending_edits == ()
    assert "Applied 2 change(s)" in state.status


def test_apply_rejects_stale_forest_before_transaction():
    controller, service, tx = make_controller()
    controller.set_pending_value("seed", 123457)
    service.forests = ()
    state = controller.apply_pending()
    assert tx.calls == []
    assert state.status == "Apply failed"
    assert "stale" in str(state.error)


def test_rows_for_domain_filters_semantic_inventory():
    controller, _, _ = make_controller()
    assert [row.name for row in controller.rows_for_domain("Distribution")] == ["seed", "distmap"]
    assert [row.name for row in controller.rows_for_domain("Transform")] == ["mirror"]
