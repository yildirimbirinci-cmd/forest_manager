from forest_manager.forest_control.transform import (
    COMPLEX_TRANSFORM_FIELDS,
    ROTATION_FIELDS,
    SCALE_FIELDS,
    TRANSLATION_FIELDS,
    TransformAdapter,
    WRITABLE_TRANSFORM_SCALARS,
)


class FakeService:
    def inventory(self, forest_name):
        names = TRANSLATION_FIELDS + ROTATION_FIELDS + SCALE_FIELDS
        return {'properties': [{'name': n, 'value': n + '_value'} for n in names]}


def test_transform_contract_counts():
    assert len(TRANSLATION_FIELDS) == 14
    assert len(ROTATION_FIELDS) == 16
    assert len(SCALE_FIELDS) == 17
    assert set(COMPLEX_TRANSFORM_FIELDS) == {'transmap','rotmap','scamap','rotprobcurve','scaprobcurve'}


def test_read_state_uses_inventory():
    state = TransformAdapter(FakeService()).read_state('F')
    assert state.translation['transxmin'] == 'transxmin_value'
    assert state.rotation['zrotmax'] == 'zrotmax_value'
    assert state.scale['scalelock'] == 'scalelock_value'


def test_writable_scalars_exclude_complex():
    for prop in COMPLEX_TRANSFORM_FIELDS:
        assert prop not in WRITABLE_TRANSFORM_SCALARS
