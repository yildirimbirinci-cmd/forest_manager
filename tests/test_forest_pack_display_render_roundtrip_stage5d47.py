from forest_manager.forest_control.display_render_effects import (
    DISPLAY_RENDER_FIELDS,
    DisplayRenderEffectsAdapter,
)


class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name': 'vmesh', 'value': 1},
            {'name': 'vmaxitems', 'value': 1000},
            {'name': 'rmesh', 'value': 0},
            {'name': 'renderMode', 'value': 2},
            {'name': 'rmaxitems', 'value': 2000},
            {'name': 'opacity', 'value': 0.75},
        ]}


def test_writability_boundary_does_not_write():
    verification = DisplayRenderEffectsAdapter(FakeService()).runtime_verify_writability('F')
    assert verification['writable_fields'] == ()
    assert verification['read_only_fields'] == DISPLAY_RENDER_FIELDS
    assert verification['operation_count'] == 0
    assert verification['runtime_probe_executed'] is False


def test_scalar_snapshot_reads_display_and_render():
    snap = DisplayRenderEffectsAdapter(FakeService()).scalar_snapshot('F')
    assert snap['vmesh'] == 1
    assert snap['rmesh'] == 0
    assert snap['opacity'] == 0.75


def test_noop_plan_preserves_snapshot():
    adapter = DisplayRenderEffectsAdapter(FakeService())
    assert adapter.no_op_display_render_plan('F') == adapter.scalar_snapshot('F')
