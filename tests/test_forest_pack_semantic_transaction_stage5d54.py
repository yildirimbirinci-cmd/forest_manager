import pytest

from forest_manager.forest_control import ForestControlError
from forest_manager.forest_control.semantic_transaction import (
    SemanticScalarChange,
    SemanticTransactionManager,
)


class Descriptor:
    def __init__(self, route="scalar_direct"):
        self.route = route


class FakeAPI:
    def __init__(self, service):
        self.service = service

    def describe(self, domain, control, raw_property):
        return Descriptor("read_only" if raw_property == "blocked" else "scalar_direct")

    def get(self, forest_name, domain, control, raw_property):
        return {"value": self.service.values[raw_property]}

    def set_scalar(self, forest_name, domain, control, raw_property, value):
        setter = getattr(self.service, "set_property", None)
        if not callable(setter):
            raise ForestControlError("ForestPackControlService has no set_property runtime endpoint")
        return setter(forest_name, raw_property, value)

    def rollback(self):
        rollback = getattr(self.service, "rollback", None)
        if not callable(rollback):
            return []
        return rollback()


class BoundaryService:
    def __init__(self):
        self.values = {"seed": 123456, "mirror": False}


class WritableService(BoundaryService):
    def __init__(self):
        super().__init__()
        self.original = dict(self.values)
        self.history = []

    def set_property(self, forest_name, raw_property, value):
        self.history.append((raw_property, self.values[raw_property]))
        self.values[raw_property] = value
        return {"ok": True, "property": raw_property}

    def rollback(self):
        results = []
        while self.history:
            raw_property, old_value = self.history.pop()
            self.values[raw_property] = old_value
            results.append({"property": raw_property, "restored": old_value})
        return results


def changes():
    return (
        SemanticScalarChange("distribution", "x", "seed", 123456),
        SemanticScalarChange("transform", "y", "mirror", False),
    )


def test_duplicate_property_rejected_before_write():
    service = BoundaryService()
    manager = SemanticTransactionManager(service, FakeAPI(service))
    duplicate = (
        SemanticScalarChange("distribution", "x", "seed", 1),
        SemanticScalarChange("distribution", "x", "seed", 2),
    )
    with pytest.raises(ForestControlError, match="Duplicate semantic transaction property"):
        manager.validate_changes(duplicate)


def test_runtime_boundary_preserves_snapshot_without_fake_operations():
    service = BoundaryService()
    manager = SemanticTransactionManager(service, FakeAPI(service))
    result = manager.apply_and_rollback("FM_Forest_001", changes())
    assert result.operation_count == 0
    assert result.blocked_operation_count == 2
    assert result.write_verified is False
    assert result.rollback_verified is True
    assert result.before_snapshot == result.after_write_snapshot == result.after_rollback_snapshot


def test_writable_service_executes_and_rolls_back_no_op_transaction():
    service = WritableService()
    manager = SemanticTransactionManager(service, FakeAPI(service))
    result = manager.apply_and_rollback("FM_Forest_001", changes())
    assert result.operation_count == 2
    assert result.blocked_operation_count == 0
    assert result.rollback_step_count == 2
    assert result.write_verified is True
    assert result.rollback_verified is True
    assert service.values == service.original
