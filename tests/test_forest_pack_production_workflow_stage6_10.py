from __future__ import annotations

import pytest

from forest_manager.forest_control.semantic_transaction import (
    ProductionControlWorkflow,
    UnifiedControlOperation,
    UnifiedControlTransactionManager,
)
from forest_manager.forest_control.service import ForestControlError, SceneUnitContext

from test_forest_pack_unified_transaction_stage6_9 import FakeUnifiedService


class FakeProductionService(FakeUnifiedService):
    def __init__(self):
        super().__init__()
        self.properties[("FM_Alt", "seed")] = {"value": 20, "value_class": "Integer", "write_mode": "scalar"}
        self.forest_names = ["FM_Forest_001", "FM_Alt"]
        self.selected = "FM_Forest_001"
        self.list_calls = 0
        self.mutate_topology_after_transaction = False

    def list_forests(self, *, preflight=True):
        self.list_calls += 1
        if self.mutate_topology_after_transaction and self.list_calls >= 2:
            return ("FM_Forest_001",)
        return tuple(self.forest_names)

    def resolve_forest_target(self, explicit_forest_name=None, *, use_selected=True, preflight=True):
        if explicit_forest_name is not None:
            if explicit_forest_name not in self.forest_names:
                raise ForestControlError(f"Explicit Forest target is stale or missing: {explicit_forest_name}")
            return explicit_forest_name
        if not use_selected:
            raise ForestControlError("selected disabled")
        if self.selected not in self.forest_names:
            raise ForestControlError("selected stale")
        return self.selected

    def scene_units(self, *, preflight=True):
        return SceneUnitContext(
            display_type="#Metric",
            display_unit="Meters",
            system_type="#Centimeters",
            system_scale=1.0,
            one_meter_system_units=100.0,
            one_centimeter_system_units=1.0,
            one_millimeter_system_units=0.1,
            sample_one_meter_display="1.0m",
        )


def _workflow(service: FakeProductionService) -> ProductionControlWorkflow:
    return ProductionControlWorkflow(service, UnifiedControlTransactionManager(service))


def test_stage6_10_selected_target_and_multi_forest_rollback():
    service = FakeProductionService()
    result = _workflow(service).apply_and_rollback([
        UnifiedControlOperation("seed", 11),
        UnifiedControlOperation("seed", 21, forest_name="FM_Alt"),
    ])
    assert result.resolved_default_forest == "FM_Forest_001"
    assert result.selected_target_used is True
    assert result.explicit_target_used is False
    assert result.transaction.operation_count == 2
    assert result.transaction.rollback_step_count == 2
    assert result.transaction.rollback_verified is True
    assert result.stale_target_guard_verified is True
    assert service.properties[("FM_Forest_001", "seed")]["value"] == 10
    assert service.properties[("FM_Alt", "seed")]["value"] == 20


def test_stage6_10_explicit_target_overrides_selected():
    service = FakeProductionService()
    result = _workflow(service).apply_and_rollback([
        UnifiedControlOperation("seed", 21),
    ], explicit_forest_name="FM_Alt")
    assert result.resolved_default_forest == "FM_Alt"
    assert result.selected_target_used is False
    assert result.explicit_target_used is True


def test_stage6_10_stale_explicit_target_blocked_before_write():
    service = FakeProductionService()
    with pytest.raises(ForestControlError, match="stale or missing"):
        _workflow(service).execute([
            UnifiedControlOperation("seed", 11),
        ], explicit_forest_name="FM_Missing")
    assert service.journal == []


def test_stage6_10_multi_forest_operation_target_prevalidated():
    service = FakeProductionService()
    with pytest.raises(ForestControlError, match="target is stale or missing"):
        _workflow(service).execute([
            UnifiedControlOperation("seed", 11),
            UnifiedControlOperation("seed", 31, forest_name="FM_Missing"),
        ])
    assert service.journal == []


def test_stage6_10_scene_unit_context_dynamic_conversion():
    service = FakeProductionService()
    units = service.scene_units()
    assert units.display_unit == "Meters"
    assert units.system_type == "#Centimeters"
    assert units.meters_to_system_units(1.0) == 100.0
    assert units.system_units_to_meters(250.0) == 2.5


def test_stage6_10_scene_topology_stale_guard_after_transaction():
    service = FakeProductionService()
    service.mutate_topology_after_transaction = True
    with pytest.raises(ForestControlError, match="topology changed"):
        _workflow(service).apply_and_rollback([
            UnifiedControlOperation("seed", 11),
        ])
    assert service.properties[("FM_Forest_001", "seed")]["value"] == 10
