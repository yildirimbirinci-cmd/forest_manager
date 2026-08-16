from forest_manager.forest_control.display_render_effects import (
    DISPLAY_FIELDS,
    EFFECT_CURVE_FIELDS,
    EFFECT_RECORD_FIELDS,
    RENDER_FIELDS,
    DisplayRenderEffectsAdapter,
)


class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name': 'vmesh', 'value': 1},
            {'name': 'vmaxitems', 'value': 1000},
            {'name': 'renderMode', 'value': 2},
            {'name': 'opacity', 'value': 0.5},
            {'name': 'efidlist', 'value': [1]},
            {'name': 'Effect_Curves', 'value': 'ReferenceTarget:CurveControl'},
        ]}


def test_read_state_uses_inventory():
    state = DisplayRenderEffectsAdapter(FakeService()).read_state('F')
    assert state.forest_name == 'F'
    assert state.display['vmesh'] == 1
    assert state.render['renderMode'] == 2
    assert state.effect_records['efidlist'] == [1]
    assert state.effect_curves['Effect_Curves'] == 'ReferenceTarget:CurveControl'


def test_field_contract_sizes():
    assert len(DISPLAY_FIELDS) == 7
    assert len(RENDER_FIELDS) == 8
    assert len(EFFECT_RECORD_FIELDS) == 32
    assert EFFECT_CURVE_FIELDS == ('Effect_Curves',)
