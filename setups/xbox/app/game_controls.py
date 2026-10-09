"""User-supplied AC8 reference; keyboard keys are physical US QWERTY positions."""
import json
from .keyboard import physical_binding
from .model import XBOX_OUTPUTS

SOURCE = 'User-supplied AC8 controls'
XBOX_NAMES = {'BACK': 'View / BACK', 'START': 'Menu / START'}
XBOX_DEFAULTS = {name: {'action': action, 'source': SOURCE} for name, action in {
    'A': 'Fire machine gun', 'B': 'Fire missile / Weapon', 'X': 'Change weapon', 'Y': 'Change target',
    'LB': 'Yaw left', 'RB': 'Yaw right', 'LT': 'Decelerate', 'RT': 'Accelerate',
    'BACK': 'Toggle radar map display', 'START': 'Pause menu on/off',
    'L3': 'Deploy flares with R3', 'R3': 'Change view; deploy flares with L3',
    'UP': 'Order: Forward attack', 'DOWN': 'Order: Cover',
    'LEFT': 'Order: Disp. atk', 'RIGHT': 'Order: SP weapons on/off',
}.items()}
KEYBOARD_DEFAULTS = {(physical_binding({'code': code, 'modifiers': []})[0], ()):
                    {'action': action, 'source': SOURCE} for code, action in {
    'KeyS': 'Ascend / Pitch up', 'KeyW': 'Descend / Pitch down',
    'KeyA': 'Turn left / Roll left', 'KeyD': 'Turn right / Roll right',
    'KeyQ': 'Yaw left', 'KeyE': 'Yaw right', 'Space': 'Accelerate', 'ControlLeft': 'Decelerate',
    'KeyJ': 'Fire machine gun', 'KeyL': 'Fire missile / Weapon',
    'KeyK': 'Change weapon / Next weapon', 'KeyI': 'Change weapon / Previous weapon',
    'Digit1': 'Standard missiles', 'Digit2': 'Special weapon 1', 'Digit3': 'Special weapon 2',
    'KeyF': 'Camera control (mouse)', 'Digit7': 'Camera up', 'Numpad8': 'Camera up',
    'Digit8': 'Camera down', 'Numpad2': 'Camera down', 'Digit9': 'Camera left', 'Numpad4': 'Camera left',
    'Digit0': 'Camera right', 'Numpad6': 'Camera right', 'KeyZ': 'Autopilot', 'KeyC': 'Autopilot',
    'KeyR': 'Gear down / Gear up', 'KeyV': 'Change view', 'KeyX': 'Deploy flares',
    'KeyT': 'Change target', 'KeyM': 'Switch radar map',
    'ArrowUp': 'Order: Forward attack', 'ArrowDown': 'Order: Cover',
    'ArrowLeft': 'Order: Disp. atk', 'ArrowRight': 'Order: SP weapons on/off',
}.items()}
UNKNOWN = 'No default action listed; set this action manually in game.'


def xbox_choices():
    return [{'value': name, 'label': f'{XBOX_NAMES.get(name, name)} ({XBOX_DEFAULTS[name]["action"] if name in XBOX_DEFAULTS else "No default action listed"})'}
            for name in XBOX_OUTPUTS]


def key_action(binding, layout, resolve):
    if not isinstance(binding, (str, dict)) or len(json.dumps(binding)) > 256:
        raise ValueError('Invalid keyboard binding.')
    if isinstance(binding, dict):
        physical_binding(binding)
    if layout is not None and (not isinstance(layout, str) or len(layout) != 8 or any(c not in '0123456789abcdef' for c in layout)):
        raise ValueError('Invalid keyboard layout.')
    if binding == '':
        return {'status': 'unassigned', 'text': 'Unassigned.'}
    if layout is None:
        return {'status': 'needs-layout', 'text': 'Choose a keyboard layout to identify this key.'}
    try:
        hid, modifiers = resolve(binding, layout)
    except ValueError as error:
        return {'status': 'unsupported', 'text': str(error)}
    entry = KEYBOARD_DEFAULTS.get((hid, tuple(sorted(modifiers))))
    return {'status': 'known' if entry else 'unknown', 'text': entry['action'] if entry else UNKNOWN}
