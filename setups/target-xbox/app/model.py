"""Mode-independent profiles, storage and pure Xbox report conversion."""
from copy import deepcopy
import json
import math
from pathlib import Path
from .keyboard import physical_binding

MODES = ('keyboard', 'xbox', 'target-xbox')
BITS = dict(zip(('UP', 'DOWN', 'LEFT', 'RIGHT', 'START', 'BACK', 'L3', 'R3', 'LB', 'RB', 'A', 'B', 'X', 'Y'),
                (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 4096, 8192, 16384, 32768)))
XBOX_OUTPUTS = ('A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'L3', 'R3', 'START', 'BACK', 'UP', 'DOWN', 'LEFT', 'RIGHT')
CONTROLS = [f's{i}' for i in range(1, 17)] + [f'q{i}' for i in range(1, 17)]
KEYS = ('roll_left', 'roll_right', 'pitch_down', 'pitch_up', 'yaw_left', 'yaw_right',
        'camera_up', 'camera_down', 'camera_left', 'camera_right', 'accelerate', 'brake')


class ConfigurationError(ValueError):
    def __init__(self, message, field):
        super().__init__(message)
        self.field = field


def defaults(mode):
    if mode not in MODES:
        raise ValueError('Choose a supported mode.')
    xbox = ['A', 'B', 'X', 'Y', '', 'L3+R3', 'R3', 'BACK', 'A', 'START',
            'UP', 'DOWN', 'LEFT', 'RIGHT', 'LB+RB', 'Y']
    keyboard = ['Space', 'e', 'Tab', 't', '', 'c', 'v', 'r', 'Enter', 'Escape',
                'F1', 'F2', 'F3', 'F4', 'a', 'f']
    values = keyboard if mode == 'keyboard' else xbox
    return {'version': 1, 'layout': None, 'buttons': dict(zip(CONTROLS, values + [values[1], values[5]] + [''] * 14)),
            'keys': dict(zip(KEYS, ('ArrowLeft', 'ArrowRight', 'ArrowDown', 'ArrowUp', 'q', 'd',
                                    'Numpad8', 'Numpad2', 'Numpad4', 'Numpad6', 'w', 's'))),
            'axes': {'roll': 0, 'pitch': 1, 'yaw': 3, 'throttle': 2 if mode == 'target-xbox' else 0},
            'invert': {'roll': False, 'pitch': True, 'yaw': False, 'throttle': True, 'camera': False},
            'deadzone': 0.04, 'throttle_deadzone': 0.07, 'yaw_threshold': 0.25,
            'camera_strength': 1.0, 'high_g_button': 5, 'poll_hz': 125}


def validate(mode, cfg):
    base = defaults(mode)
    if not isinstance(cfg, dict) or set(cfg) != set(base) or type(cfg['version']) is not int or cfg['version'] != 1:
        raise ValueError('Unsupported profile fields or version.')
    if mode == 'keyboard':
        layout = cfg['layout']
        if not isinstance(layout, str) or len(layout) != 8 or any(c not in '0123456789abcdef' for c in layout):
            raise ConfigurationError('Choose an installed keyboard layout.', 'layout')
    elif cfg['layout'] is not None:
        raise ConfigurationError('Xbox profiles do not use a keyboard layout.', 'layout')
    for key in ('axes', 'invert', 'buttons', 'keys'):
        if not isinstance(cfg[key], dict) or set(cfg[key]) != set(base[key]):
            raise ValueError(f'Unexpected {key} fields.')
    for key, value in cfg['axes'].items():
        if type(value) is not int or not 0 <= value < 6:
            raise ConfigurationError('Axis indices must be between 0 and 5.', f'axes:{key}')
    for key, value in cfg['invert'].items():
        if type(value) is not bool:
            raise ConfigurationError('Axis inversion must be true or false.', f'invert:{key}')
    for key, label, low, high, unit in (('deadzone', 'Stick deadzone', 0, 0.99, ''),
                                       ('throttle_deadzone', 'Throttle deadzone', 0, 0.99, ''),
                                       ('yaw_threshold', 'Yaw threshold', 0.01, 1, ''),
                                       ('camera_strength', 'Camera strength', 0, 1, ''),
                                       ('poll_hz', 'Polling rate', 10, 500, ' Hz')):
        if type(cfg[key]) not in (int, float) or not math.isfinite(cfg[key]) or not low <= cfg[key] <= high:
            raise ConfigurationError(f'{label} must be between {low} and {high}{unit}.', key)
    if type(cfg['high_g_button']) is not int or not 0 <= cfg['high_g_button'] <= 16:
        raise ConfigurationError('High-G button must be 0 (disabled) or 1–16.', 'high_g_button')
    for section in ('buttons', 'keys'):
        for key, value in cfg[section].items():
            field = f'{section}:{key}'
            if not isinstance(value, (str, dict)) or len(json.dumps(value)) > 256:
                raise ConfigurationError('Invalid binding.', field)
            if isinstance(value, dict):
                try:
                    physical_binding(value)
                except ValueError as error:
                    raise ConfigurationError(str(error), field) from error
            if section == 'buttons' and mode != 'keyboard' and value != '' and (not isinstance(value, str) or any(n not in XBOX_OUTPUTS for n in value.split('+'))):
                raise ConfigurationError('Use Xbox button names separated by +, or leave unassigned.', field)
    return cfg


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.local = self.root / '.local'
        self.path = self.local / 'config.json'

    def load(self):
        state = {'version': 1, 'preferred_mode': None, 'target_path': '',
                 'profiles': {m: defaults(m) for m in MODES}}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or set(data) != set(state) or data['version'] != 1 or data['preferred_mode'] not in (None, *MODES):
                raise ValueError('Local settings are invalid. Restore the backup or configure again.')
            if not isinstance(data['profiles'], dict):
                raise ValueError('Local profiles are invalid.')
            for mode, profile in data['profiles'].items():
                if profile != defaults(mode):
                    validate(mode, profile)
            if set(data['profiles']) != set(MODES) or not isinstance(data['target_path'], str):
                raise ValueError('Local settings are incomplete.')
            state = data
        return state

    def save(self, mode, profile, target_path):
        validate(mode, profile)
        if not isinstance(target_path, str) or len(target_path) > 1024 or '\x00' in target_path:
            raise ValueError('Invalid TARGET installation path.')
        data = self.load()
        data.update(preferred_mode=mode, target_path=target_path)
        data['profiles'][mode] = deepcopy(profile)
        self.local.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            (self.local / 'config.previous.json').write_bytes(self.path.read_bytes())
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        tmp.replace(self.path)
        return data


def centered(value, deadzone):
    value = max(-1, min(1, value))
    if abs(value) <= deadzone:
        return 0.0
    return math.copysign((abs(value) - deadzone) / (1 - deadzone), value)


class ThrottleSelector:
    """Last meaningful movement wins; simultaneous samples keep ownership."""
    def __init__(self):
        self.previous = None
        self.active = 1  # Quadrant preserves the existing startup position.

    def read(self, stick, quadrant):
        values = [stick, quadrant]
        if self.previous is None:
            self.previous = values.copy()
        moved = []
        for index, value in enumerate(values):
            if abs(value - self.previous[index]) > .02:  # 1% of full [-1, 1] travel.
                self.previous[index] = value
                moved.append(index)
        if len(moved) == 1:
            self.active = moved[0]
        return values[self.active]


def report(state, cfg, *, throttle=None):
    stick, quadrant = state['stick'], state['quadrant']
    result = {}
    for name, output in (('roll', 'lx'), ('pitch', 'ly')):
        value = centered(stick['axes'][cfg['axes'][name]], cfg['deadzone'])
        result[output] = -value if cfg['invert'][name] else value
    if throttle is None:
        throttle = quadrant['axes'][cfg['axes']['throttle']]
    throttle = centered(-throttle if cfg['invert']['throttle'] else throttle, cfg['throttle_deadzone'])
    result.update(lt=max(0, -throttle), rt=max(0, throttle), rx=stick['hat'][0] * cfg['camera_strength'],
                  ry=stick['hat'][1] * cfg['camera_strength'] * (-1 if cfg['invert']['camera'] else 1))
    if cfg['high_g_button'] in stick['buttons']:
        result['lt'] = result['rt'] = 1
    mask = 0
    for prefix, source in (('s', stick), ('q', quadrant)):
        for button in source['buttons']:
            binding = cfg['buttons'].get(f'{prefix}{button}', '')
            for name in filter(None, binding.split('+')):
                if name in ('LT', 'RT'):
                    result[name.lower()] = 1
                else:
                    mask |= BITS[name]
    yaw = stick['axes'][cfg['axes']['yaw']] * (-1 if cfg['invert']['yaw'] else 1)
    if yaw < -cfg['yaw_threshold']:
        mask |= BITS['LB']
    elif yaw > cfg['yaw_threshold']:
        mask |= BITS['RB']
    result['buttons'] = mask
    return result
