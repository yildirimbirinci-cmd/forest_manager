from __future__ import annotations

import pytest

from forest_manager.forest_control.area_records import AreaBoundaryRecord, AreaBoundaryUpdate
from forest_manager.forest_control.boundary_semantics import BoundaryBehaviorPlanner
from forest_manager.forest_control.service import ForestControlError


def record(*, width=10.0):
    return AreaBoundaryRecord(
        index=0, area_id=1, active=1, name="Front", node_name="Line001", area_type=0,
        include_exclude=0, width=width, threshold=100.0, density_falloff=100.0,
        scale_falloff=100.0, boundary_check=0, project_mode=2, obstacle_scale=100.0,
        scale_min=100.0, scale_max=100.0, z_offset=0.0,
    )


class FakeAdapter:
    def __init__(self, rec=None):
        self.record = rec or record()
        self.applied = None

    def read_record(self, forest_name, area_index):
        assert forest_name == "FM_Forest_001"
        assert area_index == self.record.index
        return self.record

    def apply_update(self, forest_name, area_index, update, *, rollback_on_success=False):
        self.applied = (forest_name, area_index, update, rollback_on_success)
        return "result"


def test_clean_edge_disables_density_and_scale_falloff_affect():
    plan = BoundaryBehaviorPlanner(FakeAdapter()).plan_record(record(), "Clean Edge")
    assert plan.executable is True
    assert plan.update == AreaBoundaryUpdate(density_falloff=0.0, scale_falloff=0.0)
    assert plan.ai_primary is True
    assert plan.artist_override_supported is True


def test_soft_edge_preserves_positive_range_and_enables_full_falloff_affect():
    plan = BoundaryBehaviorPlanner(FakeAdapter()).plan_record(record(width=25.0), "Soft Edge")
    assert plan.executable is True
    assert plan.update == AreaBoundaryUpdate(width=25.0, density_falloff=100.0, scale_falloff=100.0)


def test_soft_edge_requires_existing_positive_range_instead_of_guessing_one():
    with pytest.raises(ForestControlError, match="must be positive"):
        BoundaryBehaviorPlanner(FakeAdapter()).plan_record(record(width=0.0), "Soft Edge")


def test_natural_spill_and_dense_screening_stay_blocked_without_required_capabilities():
    planner = BoundaryBehaviorPlanner(FakeAdapter())
    spill = planner.plan_record(record(), "Natural Spill")
    screen = planner.plan_record(record(), "Dense Screening")
    assert spill.executable is False
    assert "curve_inversion" in spill.blocked_reasons[0]
    assert screen.executable is False
    assert "density_distribution" in screen.blocked_reasons[0]


def test_apply_uses_area_record_adapter_and_rollback_flag():
    adapter = FakeAdapter()
    planner = BoundaryBehaviorPlanner(adapter)
    assert planner.apply("FM_Forest_001", 0, "Clean Edge", rollback_on_success=True) == "result"
    assert adapter.applied == (
        "FM_Forest_001", 0,
        AreaBoundaryUpdate(density_falloff=0.0, scale_falloff=0.0), True,
    )


def test_apply_rejects_blocked_boundary_intent():
    planner = BoundaryBehaviorPlanner(FakeAdapter())
    with pytest.raises(ForestControlError, match="not executable"):
        planner.apply("FM_Forest_001", 0, "Natural Spill")
