from forest_manager.forest_control.transform import TransformAdapter, WRITABLE_TRANSFORM_SCALARS


class FakeService:
    def inventory(self, forest_name):
        return {'properties': [{'name': n, 'value': i} for i, n in enumerate(WRITABLE_TRANSFORM_SCALARS)]}


def test_no_op_plan_matches_scalar_snapshot():
    adapter = TransformAdapter(FakeService())
    assert adapter.no_op_scalar_plan('F') == adapter.scalar_snapshot('F')


def test_no_op_plan_contains_only_scalar_fields():
    plan = TransformAdapter(FakeService()).no_op_scalar_plan('F')
    assert tuple(plan.keys()) == WRITABLE_TRANSFORM_SCALARS


def test_adapter_does_not_require_write_api():
    adapter = TransformAdapter(FakeService())
    adapter.no_op_scalar_plan('F')
