"""Generate original TARGET scripts; official headers stay in TARGET installation."""
from pathlib import Path
import re
from .keyboard import MOD_FLAGS
from .model import validate, KEYS

TEMPLATES = Path(__file__).parent / 'templates'
AXES = ('JOYX', 'JOYY', 'THR', 'RUDDER', 'IN_POSITION_AXIS_RY', 'IN_POSITION_AXIS_RX')
KEY_NAMES = ('FLIGHT_ROLL_LEFT', 'FLIGHT_ROLL_RIGHT', 'FLIGHT_PITCH_DOWN', 'FLIGHT_PITCH_UP',
             'FLIGHT_YAW_LEFT', 'FLIGHT_YAW_RIGHT', 'CAMERA_UP', 'CAMERA_DOWN', 'CAMERA_LEFT',
             'CAMERA_RIGHT', 'ACTION_ACCEL', 'ACTION_BRAKE')


def hid(binding, layout, resolver):
    if binding == '':
        return 0
    key, modifiers = resolver(binding, layout)
    if not 1000 <= key < 1500:
        raise ValueError('Invalid HID key value.')
    for modifier in modifiers:
        key |= MOD_FLAGS[modifier]
    return key


def generate(mode, cfg, local, nonce, resolver=None, copilot=False):
    validate(mode, cfg)
    if mode not in ('keyboard', 'target-xbox') or not re.fullmatch('[a-z0-9]+', nonce):
        raise ValueError('Invalid TARGET session.')
    text = (TEMPLATES / f'{mode}.tmc').read_text(encoding='utf-8')
    outputs = set()
    if mode == 'keyboard':
        definitions = {'KEYBOARD_CONFIGURED': 1, 'REVERSE_PITCH': int(cfg['invert']['pitch']),
                       'REVERSE_THROTTLE': int(not cfg['invert']['throttle'])}
        definitions.update({name: hid(cfg['keys'][key], cfg['layout'], resolver) for name, key in zip(KEY_NAMES, KEYS)})
        outputs.update(definitions[name] for name in KEY_NAMES)
        for name, value in definitions.items():
            text, count = re.subn(r'^define ' + re.escape(name) + r' .*$', f'define {name} {value}', text, flags=re.M)
            if count != 1:
                raise ValueError('Keyboard template does not match this configuration version.')
        start = text.index('    MapKey(&A320Pilot, TS1,')
        end = text.index('    printf("AC8 TCA profile', start)
        bindings = []
        for prefix, device in (('s', 'A320Pilot'), ('q', 'TCAQuadrant12')):
            for number in range(1, 17):
                value = hid(cfg['buttons'][f'{prefix}{number}'], cfg['layout'], resolver)
                outputs.add(value)
                bindings.append(f'    MapKey(&{device}, {number-1}, {value});')
        bindings += [f'    MapKey(&A320Pilot, H1{direction}, CAMERA_{key});'
                     for direction, key in (('U', 'UP'), ('D', 'DOWN'), ('L', 'LEFT'), ('R', 'RIGHT'))]
        text = text[:start] + '\n'.join(bindings) + '\n' + text[end:]
        text = text.replace('(x == B5)', f'(x == {cfg["high_g_button"] - 1})')
        text = text.replace('4587', str(round(cfg['throttle_deadzone'] * 32767)))
        dz = round(cfg['deadzone'] * 50)
        text = text.replace('0,46,54,100', f'0,{50-dz},{50+dz},100')
        yd = round(cfg['yaw_threshold'] * 50)
        text = text.replace('0,41,59,100', f'0,{50-yd},{50+yd},100')
        mapped_axes = {old: AXES[cfg['axes'][semantic]] for semantic, old in (('roll', 'JOYX'), ('pitch', 'JOYY'), ('yaw', 'RUDDER'))}
        text = re.sub(r'KeyAxis\(&A320Pilot, (JOYX|JOYY|RUDDER)', lambda match: 'KeyAxis(&A320Pilot, ' + mapped_axes[match[1]], text)
        text = text.replace('QT_LEFT', AXES[cfg['axes']['throttle']])
        if cfg['invert']['roll']:
            text = text.replace('FLIGHT_ROLL_LEFT,0,FLIGHT_ROLL_RIGHT', 'FLIGHT_ROLL_RIGHT,0,FLIGHT_ROLL_LEFT')
        if cfg['invert']['yaw']:
            text = text.replace('FLIGHT_YAW_LEFT,0,FLIGHT_YAW_RIGHT', 'FLIGHT_YAW_RIGHT,0,FLIGHT_YAW_LEFT')
        if cfg['invert']['camera']:
            text = text.replace('H1U, CAMERA_UP', 'H1U, CAMERA_DOWN').replace('H1D, CAMERA_DOWN', 'H1D, CAMERA_UP')
    else:
        text = text.replace('ButtonsNumber = 18', 'ButtonsNumber = 32').replace('ButtonsNumber != 18', 'ButtonsNumber != 32')
        text = text.replace('    MapKey(&TCAQuadrant12, QT_BTN1, DX17);\n    MapKey(&TCAQuadrant12, QT_BTN2, DX18);',
                            '    i = 0;\n    while(i < 16) { MapKey(&TCAQuadrant12, i, DX17+i); i=i+1; }')
    text = text.replace('include "throttle.tmh"', (TEMPLATES / 'throttle.tmh').read_text(encoding='utf-8'))
    if copilot:
        text = text.replace('Configure(&A320Copilot, MODE_EXCLUDED);', 'Configure(&EXCLUDEDSTICK, MODE_EXCLUDED);')
        text = text.replace('A320Pilot', 'A320Copilot').replace('EXCLUDEDSTICK', 'A320Pilot')
    ready = (Path(local).resolve() / f'{nonce}.ready').as_posix()
    stop = (Path(local).resolve() / f'{nonce}.stop').as_posix()
    if any(ch in ready + stop for ch in ('"', '\n', '\r')):
        raise ValueError('The project path contains characters TARGET cannot represent.')
    token_chars = '\n'.join(f'    fputc({ord(ch)}, file);' for ch in nonce)
    release_keys = '\n'.join(f'        ActKey({value});' for value in sorted(outputs - {0}))
    support = f'''\nint CheckStop(int unused)\n{{\n    int file = fopen("{stop}", "r");\n    if(file) {{\n        fclose(file);\n{release_keys}\n        file = fopen("{ready}", "w");\n        if(file) {{ fputc(48, file); fclose(file); }}\n        Abort(); return 0;\n    }}\n    file = fopen("{ready}", "w");\n    if(!file) {{ Abort(); return 1; }}\n{token_chars}\n    fclose(file);\n    DeferCall(100, &CheckStop, 0);\n}}\nint ProfileReady()\n{{\n    int file = fopen("{ready}", "w");\n    if(!file) {{ Abort(); return 1; }}\n{token_chars}\n    fclose(file);\n    DeferCall(100, &CheckStop, 0);\n}}\n'''
    start = text.index('int main()')
    end = text.index('\nint EventHandle', start)
    close = text.rfind('return 0;', start, end) if mode == 'target-xbox' else text.rfind('}', start, end)
    text = text[:close] + '    ProfileReady();\n' + text[close:]
    return text + support
