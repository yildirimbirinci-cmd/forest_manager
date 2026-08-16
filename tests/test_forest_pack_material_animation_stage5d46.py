from forest_manager.forest_control.material_animation import MaterialAnimationAdapter

class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name':'tintmixmode','value':1},
            {'name':'tintcolor1','value':{'r':1,'g':2,'b':3}},
            {'name':'mathue','value':0.0},
            {'name':'animation','value':False},
            {'name':'animstart','value':{'native':'0f'}},
        ]}

def test_read_state_uses_inventory():
    state = MaterialAnimationAdapter(FakeService()).read_state('F')
    assert state.forest_name == 'F'
    assert state.tint['tintmixmode'] == 1
    assert state.material_adjustment['mathue'] == 0.0
    assert state.animation['animation'] is False

def test_missing_values_are_none():
    state = MaterialAnimationAdapter(FakeService()).read_state('F')
    assert state.tint['tintmap'] is None
