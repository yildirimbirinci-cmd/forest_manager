from __future__ import annotations

import pytest

from forest_manager.forest_control.semantic_transaction import (
    UnifiedControlOperation,
    UnifiedControlTransactionManager,
)
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakeUnifiedService:
    TEXTURE_REFERENCE_PROPERTIES = {"distmap"}
    NODE_REFERENCE_ARRAY_PROPERTIES = {"arnodelist"}
    MATERIAL_REFERENCE_ARRAY_PROPERTIES = {"matlist"}
    CPROXY_REFERENCE_ARRAY_PROPERTIES = {"cobjlist"}

    def __init__(self):
        self.properties = {
            ("FM_Forest_001", "seed"): {"value": 10, "value_class": "Integer", "write_mode": "scalar"},
            ("FM_Forest_001", "tintcolor1"): {"value": [10.0, 20.0, 30.0], "value_class": "Color", "write_mode": "color"},
        }
        self.arrays = {
            ("FM_Forest_001", "ScaleList"): [100.0],
            ("FM_Forest_001", "cobjlist"): ["ProxyA", "ProxyB"],
        }
        self.journal = []
        self.fail_property = None

    def rollback_marker(self):
        return len(self.journal)

    @staticmethod
    def _scalar_type_for(value_class, value):
        if value_class == "Integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ForestControlError("Integer property requires int")
            return "int", str(value)
        if value_class == "Float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ForestControlError("Float property requires number")
            return "float", str(value)
        raise ForestControlError(f"Unsupported scalar value class: {value_class}")

    @staticmethod
    def _normalize_color(value):
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ForestControlError("Color property requires RGB triplet")
        return tuple(float(v) for v in value)

    @staticmethod
    def _normalize_point3(value):
        return FakeUnifiedService._normalize_color(value)

    @staticmethod
    def _normalize_node_reference(value):
        return value

    @staticmethod
    def _normalize_material_reference(value):
        return value

    @staticmethod
    def _normalize_cproxy_reference(value):
        if value is not None and not isinstance(value, str):
            raise ForestControlError("CProxy reference requires name")
        return value

    @staticmethod
    def _normalize_texture_reference(value):
        return value

    def get_property(self, forest, prop, *, preflight=True):
        return dict(self.properties[(forest, prop)])

    def get_texture_reference(self, forest, prop, *, preflight=True):
        raise AssertionError("not used")

    def get_array_element(self, forest, prop, index, *, preflight=True):
        value = self.arrays[(forest, prop)][index]
        if prop == "ScaleList":
            return {"value": value, "value_class": "Float", "reference_type": "", "count": 1}
        return {"value": value, "value_class": "CProxy", "reference_type": "cproxy", "count": 2}

    def set_property(self, forest, prop, value, *, preflight=True):
        if self.fail_property == prop:
            raise ForestControlError("injected write failure")
        row = self.properties[(forest, prop)]
        self.journal.append(("property", forest, prop, row["value"]))
        row["value"] = list(value) if isinstance(value, tuple) else value
        return {"verified": True}

    def set_array_element(self, forest, prop, index, value, *, preflight=True):
        if self.fail_property == prop:
            raise ForestControlError("injected write failure")
        values = self.arrays[(forest, prop)]
        self.journal.append(("array", forest, prop, index, values[index]))
        values[index] = value
        return {"verified": True}

    def rollback_to(self, marker):
        steps = []
        for entry in reversed(self.journal[marker:]):
            if entry[0] == "property":
                _, forest, prop, old = entry
                self.properties[(forest, prop)]["value"] = old
                steps.append({"property_name": prop, "restored": old, "verified": True})
            else:
                _, forest, prop, index, old = entry
                self.arrays[(forest, prop)][index] = old
                steps.append({"property_name": prop, "index": index, "restored": old, "verified": True})
        del self.journal[marker:]
        return steps


def test_unified_mixed_transaction_apply_and_rollback():
    service = FakeUnifiedService()
    manager = UnifiedControlTransactionManager(service)
    result = manager.apply_and_rollback([
        UnifiedControlOperation("seed", 11),
        UnifiedControlOperation("tintcolor1", [11, 20, 30]),
        UnifiedControlOperation("ScaleList", 101.0, index=0),
        UnifiedControlOperation("cobjlist", "ProxyB", index=0),
    ], default_forest_name="FM_Forest_001")
    assert result.operation_count == 4
    assert result.rollback_step_count == 4
    assert result.write_verified is True
    assert result.rollback_verified is True
    assert result.rolled_back_on_success is True
    assert service.properties[("FM_Forest_001", "seed")]["value"] == 10
    assert service.arrays[("FM_Forest_001", "ScaleList")][0] == 100.0
    assert service.arrays[("FM_Forest_001", "cobjlist")][0] == "ProxyA"


def test_unified_prevalidation_blocks_duplicate_without_writes():
    service = FakeUnifiedService()
    manager = UnifiedControlTransactionManager(service)
    with pytest.raises(ForestControlError, match="Duplicate unified transaction target"):
        manager.validate_operations([
            UnifiedControlOperation("seed", 11),
            UnifiedControlOperation("seed", 12),
        ], default_forest_name="FM_Forest_001")
    assert service.journal == []
    assert service.properties[("FM_Forest_001", "seed")]["value"] == 10


def test_unified_partial_failure_rolls_back_only_transaction_scope():
    service = FakeUnifiedService()
    service.journal.append(("property", "FM_Forest_001", "seed", 9))
    manager = UnifiedControlTransactionManager(service)
    service.fail_property = "ScaleList"
    with pytest.raises(ForestControlError, match="injected write failure"):
        manager.execute([
            UnifiedControlOperation("seed", 11),
            UnifiedControlOperation("ScaleList", 101.0, index=0),
        ], default_forest_name="FM_Forest_001")
    assert len(service.journal) == 1
    assert service.properties[("FM_Forest_001", "seed")]["value"] == 10
    assert service.arrays[("FM_Forest_001", "ScaleList")][0] == 100.0


def test_unified_explicit_forest_overrides_default():
    service = FakeUnifiedService()
    service.properties[("FM_Alt", "seed")] = {"value": 20, "value_class": "Integer", "write_mode": "scalar"}
    manager = UnifiedControlTransactionManager(service)
    validated = manager.validate_operations([
        UnifiedControlOperation("seed", 21, forest_name="FM_Alt")
    ], default_forest_name="FM_Forest_001")
    assert validated[0]["forest_name"] == "FM_Alt"


def test_service_scoped_rollback_marker_contract():
    service = ForestPackControlService()
    service._rollback_journal = [
        {"forest_name": "A", "property_name": "seed", "value_class": "Integer", "write_mode": "scalar", "value": 1},
        {"forest_name": "A", "property_name": "seed", "value_class": "Integer", "write_mode": "scalar", "value": 2},
    ]
    marker = 1
    service._send_scalar = lambda *args, **kwargs: {"verified": True}
    steps = service.rollback_to(marker)
    assert len(steps) == 1
    assert service.rollback_marker() == 1
    assert service._rollback_journal[0]["value"] == 1
