from forest_manager.forest_control.surface_camera import (
    COMPLEX_SURFACE_CAMERA_FIELDS,
    WRITABLE_SURFACE_CAMERA_SCALARS,
    SurfaceCameraAdapter,
)


class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name': 'altmin', 'value': 10.0}, {'name': 'altmax', 'value': 20.0},
            {'name': 'slopemin', 'value': 0.0}, {'name': 'slopemax', 'value': 45.0},
            {'name': 'uvmultscalex', 'value': 100.0}, {'name': 'uvmultscaley', 'value': 100.0},
            {'name': 'camlimit', 'value': True}, {'name': 'camlod', 'value': False},
            {'name': 'camnear', 'value': 100.0}, {'name': 'camfar', 'value': 1000.0},
            {'name': 'camera', 'value': 'Camera001'}, {'name': 'lookattarget', 'value': 'Target001'},
        ]}


def test_no_op_plan_matches_scalar_snapshot():
    adapter = SurfaceCameraAdapter(FakeService())
    assert adapter.no_op_scalar_plan('F') == adapter.scalar_snapshot('F')


def test_complex_fields_not_in_scalar_plan():
    assert all(field not in WRITABLE_SURFACE_CAMERA_SCALARS for field in COMPLEX_SURFACE_CAMERA_FIELDS)


def test_no_write_api_exposed_by_adapter_boundary():
    adapter = SurfaceCameraAdapter(FakeService())
    assert not hasattr(adapter, 'update_scalars')
