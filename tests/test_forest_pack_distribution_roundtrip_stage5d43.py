import pytest

from forest_manager.forest_control.distribution import DISTRIBUTION_COMPLEX, DISTRIBUTION_SCALARS, DistributionAdapter


class FakeService:
    def inventory(self, forest_name):
        return {
            "properties": [
                {"name": prop, "value": prop}
                for prop in DISTRIBUTION_SCALARS + DISTRIBUTION_COMPLEX
            ]
        }


def test_no_op_plan_matches_current_scalar_snapshot():
    adapter = DistributionAdapter(FakeService())
    state = adapter.read_state("ForestA")
    expected = {prop: state.values.get(prop) for prop in DISTRIBUTION_SCALARS}
    assert adapter.no_op_scalar_plan("ForestA") == expected


def test_update_scalars_rejects_complex_property():
    adapter = DistributionAdapter(FakeService())
    with pytest.raises(ValueError):
        adapter.update_scalars("ForestA", {"distmap": "x"})


def test_update_scalars_exposes_verified_write_boundary():
    adapter = DistributionAdapter(FakeService())
    with pytest.raises(RuntimeError, match="write is unavailable"):
        adapter.update_scalars("ForestA", {"units_x": 75.0})
