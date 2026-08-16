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
        self.forests = ("FM_Forest_001", "FM_Forest_002")
        self.selected = "FM_Forest_002"
        self.fail = False

    def list_forests(self, *, preflight: bool = True):
        if self.fail:
            raise RuntimeError("bridge offline")
        return self.forests

    def scene_units(self, *, preflight: bool = True):
        return FakeUnits()

    def selected_forest_name(self, *, preflight: bool = True):
        if self.selected not in self.forests:
            raise ForestControlError("not a forest")
        return self.selected

    def inventory(self, forest_name: str, *, preflight: bool = True):
        if forest_name not in self.forests:
            raise ForestControlError("missing forest")
        return {
            "forest_name": forest_name,
            "property_count": 2,
            "properties": [
                {"name": "seed", "value_class": "Integer", "write_mode": "scalar", "readable": True, "value": 123456},
                {"name": "distmap", "value_class": "Bitmaptexture", "write_mode": "read_only", "readable": True, "value": None},
            ],
        }


def test_refresh_prefers_current_max_forest_selection():
    service = FakeService()
    controller = ForestManagerUIController(service)
    state = controller.refresh_scene()
    assert state.bridge_online is True
    assert state.selected_forest == "FM_Forest_002"
    assert state.forest_names == service.forests
    assert len(state.properties) == 2
    assert state.scene_units["display_unit"] == "meters"
    assert state.scene_units["system_type"] == "centimeters"


def test_refresh_falls_back_to_first_forest_when_max_selection_is_not_forest():
    service = FakeService()
    service.selected = "Line001"
    controller = ForestManagerUIController(service)
    state = controller.refresh_scene()
    assert state.selected_forest == "FM_Forest_001"
    assert state.error is None


def test_select_forest_loads_inventory_without_writes():
    service = FakeService()
    controller = ForestManagerUIController(service)
    controller.refresh_scene(prefer_max_selection=False)
    state = controller.select_forest("FM_Forest_002")
    assert state.selected_forest == "FM_Forest_002"
    assert [row.name for row in state.properties] == ["seed", "distmap"]
    assert [row.write_mode for row in state.properties] == ["scalar", "read_only"]


def test_stale_explicit_ui_selection_is_rejected_without_losing_previous_state():
    service = FakeService()
    controller = ForestManagerUIController(service)
    before = controller.refresh_scene(prefer_max_selection=False)
    state = controller.select_forest("MissingForest")
    assert state.selected_forest == before.selected_forest
    assert state.status == "Forest selection failed"
    assert "stale or missing" in str(state.error)


def test_backend_failure_becomes_non_crashing_offline_state():
    service = FakeService()
    controller = ForestManagerUIController(service)
    controller.refresh_scene()
    service.fail = True
    state = controller.refresh_scene()
    assert state.bridge_online is False
    assert state.status == "Forest Manager backend unavailable"
    assert "bridge offline" in str(state.error)
