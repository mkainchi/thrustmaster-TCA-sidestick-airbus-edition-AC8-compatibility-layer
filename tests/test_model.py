import json
import pytest
from app.model import defaults, validate, Store, report


def test_layout_requires_explicit_choice_and_profiles_are_independent(tmp_path):
    store = Store(tmp_path)
    assert store.load()['preferred_mode'] is None
    cfg = defaults('keyboard')
    with pytest.raises(ValueError, match='layout'):
        validate('keyboard', cfg)
    cfg['layout'] = '00000409'
    store.save('keyboard', cfg, '')
    assert store.load()['preferred_mode'] == 'keyboard'
    assert store.load()['profiles']['xbox'] == defaults('xbox')
    assert store.load()['profiles']['keyboard']['layout'] == '00000409'


def test_flight_hat_and_high_g_outputs_are_independent():
    cfg = defaults('xbox')
    state = {'stick': {'axes': [1, -1, 0, 0, 0, 0], 'buttons': [5], 'hat': [1, 0]},
             'quadrant': {'axes': [-1, 0, 0, 0, 0, 0], 'buttons': [], 'hat': [0, 0]}}
    result = report(state, cfg)
    assert result['lx'] == 1 and result['ly'] == 1
    assert result['rx'] == 1 and result['ry'] == 0
    assert result['lt'] == result['rt'] == 1
    state['stick']['buttons'] = []
    result = report(state, cfg)
    assert result['rt'] == 1 and result['lt'] == 0


@pytest.mark.parametrize('change', [
    lambda c:c.update(extra=True), lambda c:c.update(version=True), lambda c:c.update(version=2),
    lambda c:c.update(layout='00000409'), lambda c:c.update(axes=[]), lambda c:c['axes'].update(roll=6),
    lambda c:c['axes'].update(roll=True), lambda c:c['invert'].update(pitch=1), lambda c:c['invert'].update(extra=True),
    lambda c:c.update(deadzone=-1), lambda c:c.update(deadzone=1), lambda c:c.update(deadzone=float('nan')),
    lambda c:c.update(camera_strength=float('inf')), lambda c:c.update(poll_hz=False), lambda c:c.update(poll_hz=501),
    lambda c:c.update(yaw_threshold=0), lambda c:c.update(high_g_button=17), lambda c:c.update(high_g_button=False),
    lambda c:c['buttons'].update(s1=1), lambda c:c['buttons'].update(s1='x'*257),
    lambda c:c['buttons'].update(s1={}), lambda c:c['buttons'].update(s1='A+BAD'),
])
def test_invalid_profiles_fail_at_trust_boundary(change):
    cfg = defaults('xbox'); change(cfg)
    with pytest.raises(ValueError): validate('xbox', cfg)


@pytest.mark.parametrize('layout',[None, '', '0000040G', 409])
def test_invalid_layout_ids(layout):
    cfg=defaults('keyboard'); cfg['layout']=layout
    with pytest.raises(ValueError): validate('keyboard',cfg)


def test_unknown_mode_nondict_and_store_backup(tmp_path):
    with pytest.raises(ValueError): defaults('unknown')
    with pytest.raises(ValueError): validate('xbox',None)
    store=Store(tmp_path); cfg=defaults('xbox')
    store.save('xbox',cfg,'')
    cfg['buttons']['s1']='B'; store.save('xbox',cfg,'')
    assert json.loads((store.local/'config.previous.json').read_text())['profiles']['xbox']['buttons']['s1']=='A'
    for path in (123,'x'*1025,'bad\x00path'):
        with pytest.raises(ValueError):store.save('xbox',cfg,path)
    saved=store.load(); saved['extra']=True; store.path.write_text(json.dumps(saved))
    with pytest.raises(ValueError):store.load()
    del saved['extra']; saved['profiles'].pop('keyboard'); store.path.write_text(json.dumps(saved))
    with pytest.raises(ValueError):store.load()


def test_buttons_yaw_camera_and_deadzone_are_recomputed():
    cfg=defaults('xbox'); cfg['invert'].update(roll=True,yaw=True,camera=True)
    cfg['buttons']['q3']='B+X'
    state={'stick':{'axes':[.5, .01, 0, 1, 0, 0],'buttons':[11,99],'hat':[-1,1]},
           'quadrant':{'axes':[1,0,0,0,0,0],'buttons':[3],'hat':[0,0]}}
    output=report(state,cfg)
    assert output['lx']<0 and output['ly']==0
    assert output['rx']==-1 and output['ry']==-1
    assert output['buttons']==1|256|8192|16384
    assert output['lt']==1
    state['stick']['axes'][3]=-1
    assert report(state,cfg)['buttons'] & 512


def test_store_rejects_malformed_state_and_captured_key(tmp_path):
    store=Store(tmp_path);store.local.mkdir()
    for value in (None,[],{'version':1,'preferred_mode':None,'profiles':None,'target_path':''}):
        store.path.write_text(json.dumps(value))
        with pytest.raises(ValueError):store.load()
    cfg=defaults('keyboard');cfg['layout']='00000409';cfg['buttons']['s1']={}
    with pytest.raises(ValueError):validate('keyboard',cfg)
    cfg['buttons']['s1']={'code':'KeyA','modifiers':['shift']}
    assert validate('keyboard',cfg)==cfg
