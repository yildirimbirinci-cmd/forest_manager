import pytest

from forest_manager.site_model import ForestPackExecutionPlan, ForestPackPlantingExecutionBridge, GeometrySourceInsertion


class _Service:
    def __init__(self):
        self.added = []
        self.removed = []
    def add_geometry_source_by_name(self, forest, source, *, preflight=True):
        self.added.append((forest, source, preflight))
        return {"forest_name": forest, "source_name": source, "geometry_index": len(self.added), "added": True, "verified": True}
    def remove_geometry_source_tail(self, forest, index, *, preflight=True):
        self.removed.append((forest, index, preflight))
        return {"verified": True}


class _FailingTransaction:
    def execute(self, operations, *, rollback_on_success=False):
        raise RuntimeError("transaction failed")


def test_source_insertions_roll_back_when_later_transaction_fails():
    service = _Service()
    bridge = ForestPackPlantingExecutionBridge(service=service, transaction=_FailingTransaction())
    plan = ForestPackExecutionPlan(1, (object(),), (), (GeometrySourceInsertion("g", "F", "SRC"),))
    with pytest.raises(RuntimeError, match="transaction failed"):
        bridge.execute(plan)
    assert service.added == [("F", "SRC", True)]
    assert service.removed == [("F", 1, False)]
