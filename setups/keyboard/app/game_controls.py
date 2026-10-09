"""Offline AC8 PC default-action hints, kept separate from editable examples.

Only verified defaults belong here. Entries carry an action and source URL;
keyboard entries additionally name the reference Windows layout, HID and sorted
modifiers in their key. No complete official PC binding table is verified yet.
"""
import json
from .keyboard import physical_binding
from .model import XBOX_OUTPUTS

XBOX_DEFAULTS = {}
KEYBOARD_DEFAULTS = {}
UNKNOWN = 'Default not verified; set this action manually in game.'


def xbox_choices():
    return [{'value': name, 'label': f'{name} ({XBOX_DEFAULTS[name]["action"] if name in XBOX_DEFAULTS else "Default unverified"})'}
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
    entry = KEYBOARD_DEFAULTS.get((layout, hid, tuple(sorted(modifiers))))
    return {'status': 'known' if entry else 'unknown', 'text': entry['action'] if entry else UNKNOWN}
