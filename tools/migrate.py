"""Import private legacy profiles while preserving their original files."""
import json
from pathlib import Path
from app.model import Store, defaults, validate
from app.target import KEY_NAMES
from app.model import KEYS

BUTTON_ACTIONS = ('ACTION_GUN','ACTION_MISSILE','ACTION_WEAPON','ACTION_TARGET','',
                  'ACTION_FLARES','ACTION_VIEW','ACTION_RADAR','ACTION_CONFIRM','ACTION_PAUSE',
                  'ACTION_WING_UP','ACTION_WING_DOWN','ACTION_WING_LEFT','ACTION_WING_RIGHT',
                  'ACTION_AUTOPILOT','ACTION_FOCUS')


def migrate(root):
    store = Store(root)
    if store.path.exists():
        return 0
    state = store.load()
    count = 0
    for mode, folder in (('keyboard','AC8_TCA_TARGET_Keyboard'),('xbox','AC8_TCA_Without_TARGET'),('target-xbox','AC8_TCA_With_TARGET')):
        filename = 'keyboard.json' if mode == 'keyboard' else 'AC8_TCA_Xbox.json'
        path = Path(root) / '.local' / 'legacy' / folder / '.local' / filename
        if not path.exists():
            continue
        old = json.loads(path.read_text(encoding='utf-8'))
        cfg = defaults(mode)
        if mode == 'keyboard':
            cfg['layout'] = old['keyboard_layout']
            cfg['invert'].update(pitch=old['reverse_pitch'], throttle=not old['reverse_throttle'])
            for number, action in enumerate(BUTTON_ACTIONS, 1):
                if action in old['bindings']:
                    cfg['buttons'][f's{number}'] = old['bindings'][action]
            for name, action in zip(KEYS, KEY_NAMES):
                cfg['keys'][name] = old['bindings'].get(action, cfg['keys'][name])
            cfg['buttons']['q1'], cfg['buttons']['q2'] = cfg['buttons']['s2'], cfg['buttons']['s6']
        else:
            for prefix, field in (('s','stick_buttons'),('q','quadrant_buttons')):
                for number, outputs in old[field].items():
                    if f'{prefix}{number}' in cfg['buttons']:
                        aliases = {'DPAD_UP':'UP','DPAD_DOWN':'DOWN','DPAD_LEFT':'LEFT','DPAD_RIGHT':'RIGHT'}
                        cfg['buttons'][f'{prefix}{number}'] = '+'.join(aliases.get(v,v) for v in outputs)
            for key in ('high_g_button','poll_hz','yaw_threshold','camera_strength','throttle_deadzone'):
                cfg[key] = old[key]
            cfg['deadzone'] = old['flight_deadzone']
            for key in ('roll','pitch','throttle'):
                cfg['invert'][key] = old['invert_'+key]
            cfg['invert']['camera'] = old['invert_camera_y']
        validate(mode, cfg)
        state['profiles'][mode] = cfg
        count += 1
    if count:
        store.local.mkdir(parents=True, exist_ok=True)
        tmp = store.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, indent=2)+'\n')
        tmp.replace(store.path)
    return count
