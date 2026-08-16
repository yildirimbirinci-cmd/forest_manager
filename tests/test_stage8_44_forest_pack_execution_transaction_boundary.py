import pytest

from forest_manager.forest_control.service import ForestControlError
from forest_manager.site_model import ForestPackPlantingExecutionBridge, GeometryKind, PlantingPlanningService, SemanticRole, SiteModelService, create_geometry


class _FakeTransaction:
    def __init__(self):
        self.calls = []

    def execute(self, operations, *, rollback_on_success=False):
        operations = tuple(operations)
        self.calls.append((operations, rollback_on_success))
        return {"verified": True, "count": len(operations)}


def test_execution_uses_one_transaction_and_blocked_plan_requires_explicit_partial_opt_in():
    service = SiteModelService()
    service.upsert_geometry(create_geometry(
        "bed",
        GeometryKind.REGION,
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        closed=True,
        metadata={"forest_name": "FM_Forest_001", "forest_distribution_density_units": 12.5},
    ))
    service.upsert_geometry(create_geometry(
        "species",
        GeometryKind.REGION,
        [(20, 0), (30, 0), (30, 10), (20, 10)],
        closed=True,
        metadata={"forest_name": "FM_Forest_001", "species": "Salvia nemorosa"},
    ))
    service.apply_artist_confirmation("bed", SemanticRole.PLANTING_BED)
    service.apply_artist_confirmation("species", SemanticRole.SPECIES_ZONE)
    plan = PlantingPlanningService().build_plan(service)
    fake = _FakeTransaction()
    bridge = ForestPackPlantingExecutionBridge(transaction=fake)
    execution = bridge.build_execution_plan(service, plan)

    with pytest.raises(ForestControlError, match="blocked directives"):
        bridge.execute(execution)
    assert fake.calls == []

    result = bridge.execute(execution, allow_partial=True, rollback_on_success=True)
    assert result.partial is True
    assert len(fake.calls) == 1
    assert len(fake.calls[0][0]) == 2
    assert fake.calls[0][1] is True
