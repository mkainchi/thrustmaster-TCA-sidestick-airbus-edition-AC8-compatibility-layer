import json
from app.model import Store
from tools.migrate import migrate


def test_private_legacy_profiles_import_without_assuming_preference(tmp_path):
    assert migrate(tmp_path) == 0
    old=tmp_path/'.local'/'legacy'/'AC8_TCA_TARGET_Keyboard'/'.local';old.mkdir(parents=True)
    original={'keyboard_layout':'00000409','reverse_pitch':False,'reverse_throttle':False,
              'bindings':{'ACTION_GUN':'g','FLIGHT_ROLL_LEFT':'ArrowLeft'}}
    (old/'keyboard.json').write_text(json.dumps(original))
    assert migrate(tmp_path)==1
    saved=Store(tmp_path).load()
    assert saved['preferred_mode'] is None
    assert saved['profiles']['keyboard']['buttons']['s1']=='g'
    assert (old/'keyboard.json').exists()
    assert migrate(tmp_path)==0


def test_both_xbox_profiles_import_aliases_calibration_and_ignore_extra_buttons(tmp_path):
    for folder in ('AC8_TCA_Without_TARGET','AC8_TCA_With_TARGET'):
        old=tmp_path/'.local/legacy'/folder/'.local';old.mkdir(parents=True)
        config={'stick_buttons':{'1':['DPAD_UP','A'],'99':['A']},'quadrant_buttons':{'2':['B']},
                'high_g_button':0,'poll_hz':100,'yaw_threshold':.3,'camera_strength':.8,'throttle_deadzone':.1,
                'flight_deadzone':.08,'invert_roll':True,'invert_pitch':False,'invert_throttle':True,'invert_camera_y':True}
        (old/'AC8_TCA_Xbox.json').write_text(json.dumps(config))
    assert migrate(tmp_path)==2
    for mode in ('xbox','target-xbox'):
        cfg=Store(tmp_path).load()['profiles'][mode]
        assert cfg['buttons']['s1']=='UP+A' and cfg['buttons']['q2']=='B'
        assert cfg['deadzone']==.08 and cfg['invert']['camera']
