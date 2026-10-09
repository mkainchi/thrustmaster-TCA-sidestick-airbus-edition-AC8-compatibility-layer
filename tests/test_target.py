from pathlib import Path
from app.model import defaults
from app.target import generate
from app import target as t
import pytest
import shutil
import subprocess
from app.dependencies import target_candidates, target_installation


def test_keyboard_generation_uses_confirmed_layout_and_private_readiness(tmp_path):
    cfg = defaults('keyboard'); cfg['layout'] = '00000409'
    script = generate('keyboard', cfg, tmp_path, 'abc123', lambda binding, layout: (1004, []))
    assert 'define KEYBOARD_CONFIGURED 1' in script
    assert 'MapKey(&A320Pilot, H1U, CAMERA_UP)' in script
    assert 'abc123' in script and 'ProfileReady();' in script
    assert 'Abort();' in script
    assert 'SetKBLayout' not in script


def test_combined_descriptor_has_32_buttons_and_4_axes(tmp_path):
    text = generate('target-xbox', defaults('target-xbox'), tmp_path, 'abc123')
    assert 'virtualj.ButtonsNumber = 32;' in text
    assert 'DX17+i' in text
    assert 'if(virtualj.ButtonsNumber != 32)' in text
    main = text[text.index('int main()'):text.index('int EventHandle')]
    assert main.index('ProfileReady();') < main.index('return 0;')
    assert text.count('fopen("' + (tmp_path / 'abc123.ready').as_posix() + '", "w")') == 3


def test_script_validation_modifiers_inversions_copilot_and_template_mismatch(tmp_path,monkeypatch):
    cfg=defaults('keyboard');cfg['layout']='00000409';cfg['invert'].update(roll=True,yaw=True,camera=True)
    cfg['axes'].update(roll=1,pitch=0)
    text=generate('keyboard',cfg,tmp_path,'nonce',lambda b,l:(1004,['ctrl','shift']),copilot=True)
    assert 'Configure(&A320Pilot, MODE_EXCLUDED);' in text
    assert 'MapKey(&A320Copilot, H1U, CAMERA_DOWN)' in text
    assert 'FLIGHT_ROLL_RIGHT,0,FLIGHT_ROLL_LEFT' in text
    assert 'FLIGHT_YAW_RIGHT,0,FLIGHT_YAW_LEFT' in text
    assert 'KeyAxis(&A320Copilot, JOYY, 0, AXMAP2(LIST(0,48,52,100), FLIGHT_ROLL_RIGHT' in text
    assert 'KeyAxis(&A320Copilot, JOYX, 0, AXMAP2(LIST(0,48,52,100), FLIGHT_PITCH_UP' in text
    assert 'ActKey(' in text[text.index('int CheckStop'):]
    with pytest.raises(ValueError):generate('keyboard',cfg,tmp_path,'bad../',lambda b,l:(1004,[]))
    with pytest.raises(ValueError):generate('xbox',defaults('xbox'),tmp_path,'valid')
    with pytest.raises(ValueError):generate('keyboard',cfg,tmp_path/'bad"folder','valid',lambda b,l:(1004,[]))
    with pytest.raises(ValueError):t.hid('a',cfg['layout'],lambda b,l:(0,[]))
    assert t.hid('',cfg['layout'],lambda b,l:(0,[]))==0
    raw=(t.TEMPLATES/'keyboard.tmc').read_text().replace('define KEYBOARD_CONFIGURED 0','define REMOVED 0')
    (tmp_path/'keyboard.tmc').write_text(raw);monkeypatch.setattr(t,'TEMPLATES',tmp_path)
    with pytest.raises(ValueError,match='template'):generate('keyboard',cfg,tmp_path,'valid',lambda b,l:(1004,[]))


@pytest.mark.parametrize('mode', ['keyboard', 'target-xbox'])
@pytest.mark.parametrize('copilot', [False, True])
@pytest.mark.parametrize('inverted', [False, True])
def test_installed_target_compiles_and_replays_shared_throttle_without_device_capture(mode, copilot, inverted):
    folder = next((p for p in target_candidates() if target_installation(p) and (p / 'Interpreter.exe').is_file()), None)
    if folder is None:
        pytest.skip('Official TARGET Interpreter is not installed; synthetic checks do not prove physical input.')
    local = Path.cwd() / '.local' / 'target-validation' / f'{mode}-{int(copilot)}-{int(inverted)}'
    local.mkdir(parents=True, exist_ok=True)
    for name in ('target.tmh', 'defines.tmh', 'sys.tmh', 'hid.tmh'):
        shutil.copyfile(folder / 'scripts' / name, local / name)
    cfg = defaults(mode)
    cfg['invert']['throttle'] = inverted
    cfg['throttle_deadzone'] = .1
    if mode == 'keyboard':
        cfg['layout'] = '00000409'
        cfg['axes']['throttle'] = 1
        cfg['buttons'].update({f's{i+1}': {'code': code, 'modifiers': []}
                               for i, code in enumerate(('PrintScreen', 'F13', 'F24', 'ControlLeft', 'ShiftRight', 'AltLeft'))})
    from app.keyboard import physical_binding
    script = generate(mode, cfg, local, 'validation', lambda b, l: physical_binding(b) if isinstance(b, dict) else (1004, []), copilot)
    if mode == 'keyboard':
        assert 'define ACTION_ACCEL 1044' in script and 'define ACTION_BRAKE 1224' in script
        assert 'ActKey(1044);' in script and 'ActKey(1224);' in script
        # Replace only generated output calls; official headers remain unchanged.
        # This records transitions without sending keys or initializing hardware.
        script = script.replace('ActKey(', 'RecordKey(').replace('int ValidateProfile()', 'int ValidateState()')
        position = script.index('int throttleZone')
        script = script[:position] + '''int recorded[16], recordedCount;
int RecordKey(int value) { recorded[recordedCount] = value; recordedCount = recordedCount + 1; }
''' + script[position:] + '''
int ValidateProfile()
{
    int result = ValidateState();
    if(result) return result;
    throttleZone = 0; highG = 0; accelHeld = 0; brakeHeld = 0; recordedCount = 0;
    ApplyThrottle();
    if(recordedCount) return 30;
    throttleZone = -1; ApplyThrottle();
    if((recordedCount != 1) | (recorded[0] != (ACTION_ACCEL | KEYON))) return 31;
    highG = 1; ApplyThrottle();
    if((recordedCount != 2) | (recorded[1] != (ACTION_BRAKE | KEYON))) return 32;
    throttleZone = 1; ApplyThrottle();
    if(recordedCount != 2) return 33;
    highG = 0; ApplyThrottle();
    if((recordedCount != 3) | (recorded[2] != ACTION_ACCEL)) return 34;
    throttleZone = 0; ApplyThrottle();
    if((recordedCount != 4) | (recorded[3] != ACTION_BRAKE)) return 35;
    throttleZone = -1; ApplyThrottle(); throttleZone = 1; ApplyThrottle();
    if((recordedCount != 7) | (recorded[4] != (ACTION_ACCEL | KEYON))) return 36;
    if((recorded[5] != ACTION_ACCEL) | (recorded[6] != (ACTION_BRAKE | KEYON))) return 37;
    throttleZone = 0; ApplyThrottle();
    if((recordedCount != 8) | (recorded[7] != ACTION_BRAKE)) return 38;
    if(accelHeld | brakeHeld) return 39;
    return 0;
}
'''
    (local / 'profile.tmc').write_text(script, encoding='utf-8')
    result = subprocess.run([str(folder / 'Interpreter.exe'), 'profile.tmc', 'ValidateProfile'], cwd=local, capture_output=True, timeout=20)
    output = (result.stdout + result.stderr).decode(errors='replace')
    assert 'ValidateProfile returned 0.' in output, output
