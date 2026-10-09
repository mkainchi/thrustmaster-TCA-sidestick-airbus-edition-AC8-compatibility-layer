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


@pytest.mark.parametrize('section,key,value,field,message', [
    (None,'layout','00000409','layout','Xbox profiles'),
    ('axes','pitch',6,'axes:pitch','between 0 and 5'),
    ('invert','pitch',1,'invert:pitch','true or false'),
    (None,'deadzone',1,'deadzone','Stick deadzone must be between 0 and 0.99'),
    (None,'throttle_deadzone',1,'throttle_deadzone','Throttle deadzone must be between 0 and 0.99'),
    (None,'yaw_threshold',0,'yaw_threshold','Yaw threshold must be between 0.01 and 1'),
    (None,'camera_strength',2,'camera_strength','Camera strength must be between 0 and 1'),
    (None,'poll_hz',501,'poll_hz','Polling rate must be between 10 and 500 Hz'),
    (None,'high_g_button',17,'high_g_button','0 (disabled) or 1–16'),
    ('buttons','s3','A+BAD','buttons:s3','Xbox button names'),
    ('buttons','s4',123,'buttons:s4','Invalid binding'),
    ('keys','roll_left',{},'keys:roll_left','Unsupported physical key'),
])
def test_validation_identifies_the_field_to_correct(section,key,value,field,message):
    cfg=defaults('xbox')
    (cfg[section] if section else cfg)[key]=value
    with pytest.raises(ValueError) as error:
        validate('xbox',cfg)
    assert getattr(error.value,'field',None)==field
    assert message in str(error.value)


def test_keyboard_layout_validation_identifies_layout_field():
    with pytest.raises(ValueError) as error:
        validate('keyboard',defaults('keyboard'))
    assert getattr(error.value,'field',None)=='layout'
def test_throttle_ownership_filters_noise_accumulates_movement_and_keeps_active_value():
    from app import model
    selector = model.ThrottleSelector()
    assert selector.read(0, .8) == .8
    assert selector.read(.01, .8) == .8
    assert selector.read(.02, .8) == .8
    assert selector.read(.021, .8) == .021
    assert selector.read(.025, .81) == .025
    assert selector.read(.025, .83) == .83
    assert selector.read(.2, .5) == .5  # Both moved: keep quadrant ownership.
    assert selector.read(-.5, .5) == -.5
    assert selector.read(-.2, .7) == -.2  # Both moved: keep stick ownership.
    assert model.ThrottleSelector().read(-1, 1) == 1


def test_selected_throttle_uses_shared_response_and_high_g_restores_current_source():
    from app import model
    cfg = model.defaults('xbox')
    cfg['throttle_deadzone'] = .1
    state = {name: {'axes': [0.] * 6, 'buttons': [], 'hat': [0, 0]} for name in ('stick', 'quadrant')}
    assert model.report(state, cfg, throttle=-1)['rt'] == 1
    assert model.report(state, cfg, throttle=1)['lt'] == 1
    assert model.report(state, cfg, throttle=.05)['rt'] == 0
    cfg['invert']['throttle'] = False
    assert model.report(state, cfg, throttle=1)['rt'] == 1
    state['stick']['buttons'] = [5]
    assert model.report(state, cfg, throttle=-1)['rt'] == 1
    state['stick']['buttons'] = []
    assert model.report(state, cfg, throttle=-1)['rt'] == 0
@pytest.mark.parametrize('mode', ['xbox', 'target-xbox'])
def test_trigger_bindings_combine_with_throttle_and_release(mode):
    from app.model import report, defaults, validate, BITS
    cfg = defaults(mode)
    cfg['buttons']['s1'] = 'A+LT'
    cfg['buttons']['q1'] = 'RT'
    validate(mode, cfg)
    state = {'stick': {'axes': [0]*6, 'hat': [0,0], 'buttons': [1]},
             'quadrant': {'axes': [0]*6, 'hat': [0,0], 'buttons': [1]}}
    out = report(state, cfg, throttle=-.5)
    assert out['lt'] == out['rt'] == 1 and out['buttons'] == BITS['A']
    state['quadrant']['buttons'] = []
    out = report(state, cfg, throttle=-.5)
    assert out['lt'] == 1 and 0 < out['rt'] < 1
    state['stick']['buttons'] = [cfg['high_g_button']]
    assert report(state, cfg, throttle=.5)['lt'] == report(state, cfg, throttle=.5)['rt'] == 1
    state['stick']['buttons'] = []
    out = report(state, cfg, throttle=.5)
    assert 0 < out['lt'] < 1 and out['rt'] == 0
def test_new_keyboard_defaults_follow_physical_reference_and_are_independent():
    cfg = defaults('keyboard')
    assert {key: binding['code'] for key,binding in cfg['keys'].items()} == dict(zip(
        cfg['keys'], ['KeyA','KeyD','KeyW','KeyS','KeyQ','KeyE','Numpad8','Numpad2','Numpad4','Numpad6','Space','ControlLeft']))
    assert [binding['code'] if binding else '' for binding in cfg['buttons'].values()] == [
        'KeyJ','KeyL','KeyK','KeyT','','KeyX','KeyV','KeyM','KeyJ','','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','','KeyT','KeyL','KeyX',*['']*14]
    assert all(binding['modifiers'] == [] for section in ('keys','buttons') for binding in cfg[section].values() if binding)
    cfg['keys']['brake']['modifiers'].append('shift')
    assert defaults('keyboard')['keys']['brake']['modifiers'] == []
    cfg['buttons']['s2']['modifiers'].append('ctrl')
    assert cfg['buttons']['q1']['modifiers'] == []


def test_legacy_unconfigured_profiles_load_unchanged_but_cannot_save_or_generate(tmp_path):
    from pathlib import Path
    legacy = json.loads((Path(__file__).parent/'fixtures/profiles.json').read_text(encoding='utf-8'))
    saved = {'version':1,'preferred_mode':'xbox','target_path':'','profiles':legacy}
    store = Store(tmp_path);store.local.mkdir();raw = json.dumps(saved).encode('utf-8');store.path.write_bytes(raw)
    assert store.load() == saved and store.path.read_bytes() == raw
    with pytest.raises(ValueError, match='layout'):store.save('keyboard', legacy['keyboard'], '')
    from app.target import generate
    with pytest.raises(ValueError, match='layout'):generate('keyboard', legacy['keyboard'], store.local, 'test', lambda *a:(1004,[]))
    store.save('xbox', defaults('xbox'), '')
    assert store.load()['profiles']['keyboard'] == legacy['keyboard']
    saved['profiles']['keyboard']['layout'] = 'invalid';store.path.write_text(json.dumps(saved),encoding='utf-8')
    with pytest.raises(ValueError, match='layout'):store.load()
