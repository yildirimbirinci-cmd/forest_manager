from forest_manager.forest_control.general_control import ForestControlEngine
from forest_manager.forest_control.semantic_transaction import SemanticScalarChange, SemanticTransactionResult


CONTROLS = (
    ("distribution", "extended_distribution_controls", "seed"),
    ("transform", "extended_transform_controls", "mirror"),
)


class FakeService:
    def list_forests(self):
        return ("FM_Forest_001",)

    def inventory(self, forest_name):
        props = [
            {"name": "seed", "value": 123456},
            {"name": "mirror", "value": False},
            {"name": "cobjlist", "array_metadata": {"count": 3}},
            {"name": "aridlist", "array_metadata": {"count": 2}},
        ]
        return {"forest_name": forest_name, "property_count": 341, "properties": props}


class FakeSemantic:
    def __init__(self):
        self.values = {"seed": 123456, "mirror": False}

    def list_domains(self):
        return tuple(f"domain_{i}" for i in range(11))

    def get(self, forest_name, domain, control, raw_property):
        return {"value": self.values[raw_property]}


class FakeTransactions:
    def apply_and_rollback(self, forest_name, changes):
        changes = tuple(changes)
        snapshot = {change.raw_property: change.value for change in changes}
        return SemanticTransactionResult(
            forest_name=forest_name,
            operation_count=0,
            blocked_operation_count=len(changes),
            rollback_step_count=0,
            write_verified=False,
            rollback_verified=True,
            before_snapshot=snapshot,
            after_write_snapshot=snapshot,
            after_rollback_snapshot=snapshot,
            runtime_write_endpoint=False,
            runtime_rollback_endpoint=False,
        )


class FakeAdapter:
    def read_record(self, forest_name, index):
        return (forest_name, index)


def make_engine():
    service = FakeService()
    semantic = FakeSemantic()
    return ForestControlEngine(
        service=service,
        semantic=semantic,
        transactions=FakeTransactions(),
        geometry=FakeAdapter(),
        areas=FakeAdapter(),
    )


def test_snapshot_and_capability_summary_use_single_facade():
    engine = make_engine()
    snapshot = engine.snapshot("FM_Forest_001", CONTROLS)
    capability = engine.capability_summary("FM_Forest_001")
    assert snapshot.semantic_values == {"seed": 123456, "mirror": False}
    assert capability["domain_count"] == 11
    assert capability["raw_property_count"] == 341
    assert capability["geometry_source_count"] == 3
    assert capability["area_record_count"] == 2
    assert capability["runtime_write_endpoint"] is False


def test_blocked_transaction_is_forwarded_without_fake_operations():
    engine = make_engine()
    changes = [
        SemanticScalarChange(domain, control, prop, engine.snapshot("FM_Forest_001", CONTROLS).semantic_values[prop])
        for domain, control, prop in CONTROLS
    ]
    result = engine.apply_scalar_transaction("FM_Forest_001", changes)
    assert result.operation_count == 0
    assert result.blocked_operation_count == 2
    assert result.rollback_verified is True
    assert result.runtime_write_endpoint is False


def test_geometry_and_area_adapters_are_exposed_by_engine():
    engine = make_engine()
    assert engine.geometry_source("FM_Forest_001", 1) == ("FM_Forest_001", 1)
    assert engine.area_record("FM_Forest_001", 1) == ("FM_Forest_001", 1)
