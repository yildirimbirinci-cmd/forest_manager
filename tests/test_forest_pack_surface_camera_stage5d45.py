from forest_manager.forest_control.surface_camera import SurfaceCameraAdapter, SurfaceCameraState


class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name': 'altmin', 'value': 10.0}, {'name': 'altmax', 'value': 20.0},
            {'name': 'spdenscurve', 'value': 'ReferenceTarget:CurveControl'},
            {'name': 'camnear', 'value': 100.0}, {'name': 'camfar', 'value': 1000.0},
            {'name': 'camdenscurve', 'value': 'ReferenceTarget:CurveControl'},
        ]}


def test_read_state_groups_fields():
    state = SurfaceCameraAdapter(FakeService()).read_state('F')
    assert isinstance(state, SurfaceCameraState)
    assert state.surface['altmin'] == 10.0
    assert state.surface_curves['spdenscurve'] == 'ReferenceTarget:CurveControl'
    assert state.camera['camfar'] == 1000.0
    assert state.camera_curves['camdenscurve'] == 'ReferenceTarget:CurveControl'


def test_read_state_uses_inventory_only():
    svc = FakeService()
    assert not hasattr(svc, 'get_property')
    SurfaceCameraAdapter(svc).read_state('F')
