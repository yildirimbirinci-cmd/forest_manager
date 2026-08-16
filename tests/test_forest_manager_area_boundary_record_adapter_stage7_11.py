from __future__ import annotations

import pytest

from forest_manager.forest_control.area_records import AreaBoundaryRecordAdapter, AreaBoundaryUpdate
from forest_manager.forest_control.semantic_transaction import UnifiedTransactionResult
from forest_manager.forest_control.service import ForestControlError


class FakeService:
    def __init__(self, mismatch: bool = False):
        self.data = {
            "aridlist": [101, 102], "pf_aractivelist": [1, 1], "arnamelist": ["Front", "Rear"],
            "arnodenamelist": ["Line001", "Line002"], "artypelist": [0, 0], "arincexclist": [0, 1],
            "arwidthlist": [10.0, 20.0], "arthresholdlist": [100.0, 100.0],
            "arflafdenslist": [100.0, 80.0], "arflafscalist": [100.0, 90.0],
            "arboundchecklist": [0, 1], "arprojectlist": [2, 2], "arobscalelist": [100.0, 100.0],
            "arscalemin": [100.0, 90.0], "arscalemax": [100.0, 110.0], "arzoffset": [0.0, 0.0],
        }
        if mismatch:
            self.data["arzoffset"] = [0.0]

    def get_property(self, forest_name, property_name, *, preflight=True):
        return {"array": {"count": len(self.data[property_name])}}

    def get_array_element(self, forest_name, property_name, index, *, preflight=True):
        value = self.data[property_name][index]
        value_class = "Float" if isinstance(value, float) else ("Integer" if isinstance(value, int) else "String")
        return {"value": value, "value_class": value_class, "verified": True}


class FakeTransaction:
    def __init__(self):
        self.validated = None
        self.executed = None

    def validate_operations(self, operations, *, default_forest_name=None):
        self.validated = tuple(operations)
        return tuple({"ok": True} for _ in self.validated)

    def execute(self, operations, *, default_forest_name=None, rollback_on_success=False):
        self.executed = tuple(operations)
        return UnifiedTransactionResult(
            default_forest_name=None, operation_count=len(self.executed), blocked_operation_count=0,
            rollback_step_count=len(self.executed) if rollback_on_success else 0,
            write_verified=True, rollback_verified=True, automatic_rollback=False,
            rolled_back_on_success=rollback_on_success, before_snapshot={}, after_write_snapshot={},
            after_rollback_snapshot={}, operations=tuple(),
        )


def test_area_record_reads_synchronized_arrays_as_one_record():
    adapter = AreaBoundaryRecordAdapter(FakeService(), FakeTransaction())
    records = adapter.list_records("FM_Forest_001")
    assert len(records) == 2
    assert records[0].name == "Front"
    assert records[0].node_name == "Line001"
    assert records[0].width == 10.0
    assert records[1].include_exclude == 1


def test_area_record_alignment_guard_blocks_mismatched_arrays():
    adapter = AreaBoundaryRecordAdapter(FakeService(mismatch=True), FakeTransaction())
    with pytest.raises(ForestControlError, match="not synchronized"):
        adapter.list_records("FM_Forest_001")


def test_area_record_patch_builds_single_index_atomic_operations():
    tx = FakeTransaction()
    adapter = AreaBoundaryRecordAdapter(FakeService(), tx)
    operations = adapter.build_update_operations(
        "FM_Forest_001", 0, AreaBoundaryUpdate(width=11.0, density_falloff=95.0)
    )
    assert [op.property_name for op in operations] == ["arwidthlist", "arflafdenslist"]
    assert {op.index for op in operations} == {0}
    assert tx.validated == operations


def test_area_record_update_uses_unified_transaction_and_optional_rollback():
    tx = FakeTransaction()
    adapter = AreaBoundaryRecordAdapter(FakeService(), tx)
    result = adapter.apply_update(
        "FM_Forest_001", 0, AreaBoundaryUpdate(width=11.0, threshold=99.0), rollback_on_success=True
    )
    assert result.operation_count == 2
    assert result.rolled_back_on_success is True
    assert [op.property_name for op in tx.executed] == ["arwidthlist", "arthresholdlist"]


def test_empty_area_record_patch_is_rejected():
    adapter = AreaBoundaryRecordAdapter(FakeService(), FakeTransaction())
    with pytest.raises(ForestControlError, match="at least one"):
        adapter.build_update_operations("FM_Forest_001", 0, AreaBoundaryUpdate())


def test_area_record_schema_promotes_atomic_adapter():
    from forest_manager.forest_control.schema import find_semantic_field
    field = find_semantic_field("areas", "area_records")
    assert field.access == "area_record_adapter"
