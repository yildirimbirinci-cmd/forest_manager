from __future__ import annotations
from dataclasses import dataclass
from forest_manager.ui.controller import ForestManagerUIController

@dataclass(frozen=True)
class FakeUnits:
    display_type:str='metric'; display_unit:str='meters'; system_type:str='centimeters'; system_scale:float=1.0
    one_meter_system_units:float=100.0; one_centimeter_system_units:float=1.0; one_millimeter_system_units:float=0.1
    sample_one_meter_display:str='1.0m'; custom_name:str=''; custom_value:float=0.0; custom_unit:str=''

class FakeService:
    def __init__(self):
        self.values={'units_x':7500.0,'units_y':7500.0,'lock_ratio':True,'clurough':0.0,'clunoise':0.0,'cluedge':0.0,'drotation':0.0,'divers':0,'distrefrandpos':True,'distpathrandpos':0.0,'applytranslation':False,'applyrotation':False,'applyscale':False}
    def list_forests(self,*,preflight=True): return ('FM_Forest_001',)
    def selected_forest_name(self,*,preflight=True): return 'FM_Forest_001'
    def scene_units(self,*,preflight=True): return FakeUnits()
    def inventory(self,forest_name,*,preflight=True):
        props=[]
        for n,v in self.values.items():
            ro=n in {'distrefrandpos','applytranslation','applyrotation','applyscale'}
            vc='Boolean' if isinstance(v,bool) else ('Integer' if isinstance(v,int) else 'Float')
            props.append({'name':n,'value_class':vc,'write_mode':'read_only' if ro else 'scalar','readable':True,'value':v})
        return {'properties':props}

@dataclass(frozen=True)
class FakeResult:
    operation_count:int; write_verified:bool=True

class FakeTx:
    def __init__(self,service): self.service=service; self.calls=[]
    def execute(self,operations,*,default_forest_name=None,rollback_on_success=False):
        ops=tuple(operations); self.calls.append((ops,default_forest_name,rollback_on_success))
        for op in ops: self.service.values[op.property_name]=op.value
        return FakeResult(len(ops))

def make_controller():
    s=FakeService(); tx=FakeTx(s); c=ForestManagerUIController(s,tx); c.refresh_scene(); return c,s,tx

def test_naturalness_is_active_and_infers_ordered_from_runtime_state():
    c,_,_=make_controller(); states={x.key:x for x in c.state.artist_controls}
    assert states['naturalness'].available is True
    assert states['naturalness'].calibration_status == 'active'
    assert states['naturalness'].value == 'Ordered'
    assert states['variation'].available is False

def test_naturalness_creates_six_synchronized_pending_changes():
    c,_,_=make_controller(); st=c.set_artist_control('naturalness','Natural')
    pending={e.property_name:e.value for e in st.pending_edits}
    assert pending == {'clurough':15.0,'clunoise':20.0,'cluedge':15.0,'drotation':30.0,'divers':25,'distpathrandpos':15.0}
    assert st.error is None

def test_spacing_and_naturalness_share_one_atomic_apply():
    c,s,tx=make_controller(); c.set_artist_control('density_spacing',60.0); c.set_artist_control('naturalness','Natural'); st=c.apply_pending()
    assert st.error is None and len(tx.calls)==1
    ops,forest,rollback=tx.calls[0]
    assert forest=='FM_Forest_001' and rollback is False
    assert {o.property_name for o in ops} == {'units_x','units_y','clurough','clunoise','cluedge','drotation','divers','distpathrandpos'}
    assert s.values['units_x']==6000.0 and s.values['clunoise']==20.0

def test_revert_restores_semantic_display_to_underlying_state():
    c,_,_=make_controller(); c.set_artist_control('naturalness','Wild'); st=c.revert_pending(); states={x.key:x for x in st.artist_controls}
    assert st.pending_edits == ()
    assert states['naturalness'].value == 'Ordered'

def test_uncalibrated_controls_are_disabled_instead_of_accepting_fake_intent():
    c,_,_=make_controller(); states={x.key:x for x in c.state.artist_controls}
    for key in ('cluster_character','species_diversity','boundary_behavior','height_character','ground_visibility'):
        assert states[key].available is False
    st=c.set_artist_control('cluster_character','Large Masses')
    assert st.status=='Artist control rejected' and st.error
