from forest_manager.forest_control.distribution import DISTRIBUTION_COMPLEX, DISTRIBUTION_SCALARS, DistributionAdapter


class FakeService:
    def inventory(self, forest_name):
        return {
            "properties": [
                {"name": prop, "value": f"{forest_name}:{prop}"}
                for prop in DISTRIBUTION_SCALARS + DISTRIBUTION_COMPLEX
            ]
        }


def test_distribution_contract_lists():
    assert len(DISTRIBUTION_SCALARS) == 25
    assert DISTRIBUTION_COMPLEX == ("distmap", "densityMap", "distpathnodes", "distrefnodes")


def test_read_state_reads_all_distribution_properties():
    state = DistributionAdapter(FakeService()).read_state("ForestA")
    assert state.forest_name == "ForestA"
    assert len(state.values) == 29
    assert state.values["units_x"] == "ForestA:units_x"
    assert state.values["distrefnodes"] == "ForestA:distrefnodes"


def test_no_op_scalar_plan_contains_only_scalars():
    plan = DistributionAdapter(FakeService()).no_op_scalar_plan("ForestA")
    assert tuple(plan) == DISTRIBUTION_SCALARS
    assert len(plan) == 25
