from forest_manager.forest_control.material_animation import MaterialAnimationAdapter, WRITABLE_SCALAR_FIELDS

class FakeService:
    def inventory(self, forest_name):
        return {'properties': [
            {'name':'tintmixmode','value':1},
            {'name':'tintcolor1','value':{'r':1,'g':2,'b':3}},
            {'name':'tintcolor2','value':{'r':4,'g':5,'b':6}},
            {'name':'matapplycolor','value':{'r':7,'g':8,'b':9}},
            {'name':'animsoffset','value':{'native':'0f'}},
            {'name':'animstart','value':{'native':'0f'}},
            {'name':'animend','value':{'native':'100f'}},
            {'name':'animation','value':False},
        ]}

def test_snapshot_partitions_values():
    snap = MaterialAnimationAdapter(FakeService()).writable_snapshot('F')
    assert set(snap) == {'scalars','colors','times'}
    assert 'tintmixmode' in WRITABLE_SCALAR_FIELDS
    assert snap['colors']['tintcolor1']['r'] == 1
    assert snap['times']['animend']['native'] == '100f'

def test_noop_plan_preserves_snapshot():
    adapter = MaterialAnimationAdapter(FakeService())
    assert adapter.no_op_writable_plan('F') == adapter.writable_snapshot('F')

def test_complex_values_not_in_scalars():
    snap = MaterialAnimationAdapter(FakeService()).writable_snapshot('F')
    assert 'tintcolor1' not in snap['scalars']
    assert 'animstart' not in snap['scalars']
    assert 'tintmap' not in snap['scalars']
