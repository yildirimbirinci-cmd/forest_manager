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
        self.values = {
            "units_x": 7500.0,
            "units_y": 7500.0,
            "lock_ratio": True,
            "clurough": 0.0,
            "clunoise": 0.0,
            "cluedge": 0.0,
            "drotation": 0.0,
            "divers": 0,
            "distrefrandpos": True,
            "distpathrandpos": 0.0,
            "clusize": 2000.0,
            "problist": None,
            "applytranslation": False,
            "applyrotation": False,
            "applyscale": False,
        }

    def list_forests(self, *, preflight=True): return ("FM_Forest_001",)
    def selected_forest_name(self, *, preflight=True): return "FM_Forest_001"
    def scene_units(self, *, preflight=True): return FakeUnits()

    def inventory(self, forest_name, *, preflight=True):
        props = []
        for name, value in self.values.items():
            if name == "problist":
                props.append({"name": name, "value_class": "ArrayParameter", "write_mode": "read_only", "readable": True, "value": None})
                continue
            ro = name in {"distrefrandpos", "applytranslation", "applyrotation", "applyscale"}
            vc = "Boolean" if isinstance(value, bool) else ("Integer" if isinstance(value, int) else "Float")
            props.append({"name": name, "value_class": vc, "write_mode": "read_only" if ro else "scalar", "readable": True, "value": value})
        return {"properties": props}


@dataclass(frozen=True)
class FakeResult:
    operation_count: int
    write_verified: bool = True


class FakeTx:
    def __init__(self, service):
        self.service = service
        self.calls = []

    def execute(self, operations, *, default_forest_name=None, rollback_on_success=False):
        ops = tuple(operations)
        self.calls.append((ops, default_forest_name, rollback_on_success))
        for op in ops:
            self.service.values[op.property_name] = op.value
        return FakeResult(len(ops))


def make_controller():
    service = FakeService()
    tx = FakeTx(service)
    controller = ForestManagerUIController(service, tx)
    controller.refresh_scene()
    return controller, service, tx


def test_cluster_character_is_active_when_four_scalar_dependencies_are_writable():
    controller, _, _ = make_controller()
    states = {item.key: item for item in controller.state.artist_controls}
    assert states["cluster_character"].available is True
    assert states["cluster_character"].calibration_status == "active"


def test_cluster_character_creates_four_pending_raw_changes():
    controller, _, _ = make_controller()
    state = controller.set_artist_control("cluster_character", "Small Groups")
    pending = {item.property_name: item.value for item in state.pending_edits}
    assert pending["clusize"] == 1000.0
    assert pending["clurough"] == 10.0
    assert pending["clunoise"] == 5.0
    assert pending["cluedge"] == 10.0
    assert state.error is None


def test_spacing_naturalness_cluster_share_single_unique_property_transaction():
    controller, _, tx = make_controller()
    controller.set_artist_control("density_spacing", 60.0)
    controller.set_artist_control("naturalness", "Natural")
    controller.set_artist_control("cluster_character", "Small Groups")
    state = controller.apply_pending()
    assert state.error is None
    assert len(tx.calls) == 1
    operations, forest_name, rollback = tx.calls[0]
    names = [op.property_name for op in operations]
    assert forest_name == "FM_Forest_001"
    assert rollback is False
    assert len(names) == len(set(names))
    assert set(names) == {
        "units_x", "units_y", "clurough", "clunoise", "cluedge",
        "drotation", "divers", "distpathrandpos", "clusize",
    }
    values = {op.property_name: op.value for op in operations}
    assert values["clurough"] == 10.0
    assert values["clunoise"] == 5.0
    assert values["cluedge"] == 10.0


def test_solitary_remains_rejected_until_disable_capability_exists():
    controller, _, _ = make_controller()
    state = controller.set_artist_control("cluster_character", "Solitary")
    assert state.status == "Artist control rejected"
    assert state.error and "cluster_disable_or_distribution_mode_capability" in state.error
