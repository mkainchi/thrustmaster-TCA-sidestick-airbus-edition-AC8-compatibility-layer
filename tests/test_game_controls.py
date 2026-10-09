from app import game_controls as g
import pytest


def test_offline_choices_use_supplied_reference_and_distinguish_flares(monkeypatch):
    choices = g.xbox_choices()
    assert len(choices) == 16
    assert {'LT', 'RT'} <= {item['value'] for item in choices}
    labels = {item['value']: item['label'] for item in choices}
    assert labels['A'] == 'A (Fire machine gun)'
    assert labels['LT'] == 'LT (Decelerate)'
    assert labels['BACK'] == 'View / BACK (Toggle radar map display)'
    assert 'with R3' in labels['L3']
    assert 'Change view' in labels['R3'] and 'with L3' in labels['R3']
    assert all(entry['source'] == 'User-supplied AC8 controls' for entry in g.XBOX_DEFAULTS.values())
    monkeypatch.setitem(g.XBOX_DEFAULTS, 'A', {'action': 'Fixture action', 'source': 'fixture'})
    assert next(item for item in g.xbox_choices() if item['value'] == 'A')['label'] == 'A (Fixture action)'
    monkeypatch.delitem(g.XBOX_DEFAULTS, 'A')
    assert next(item for item in g.xbox_choices() if item['value'] == 'A')['label'] == 'A (No default action listed)'


def test_key_actions_resolve_layout_without_emitting_or_guessing(monkeypatch):
    calls = []
    def resolve(binding, layout):
        calls.append((binding, layout))
        return 1004, ['ctrl', 'shift']
    assert g.key_action('', None, resolve)['status'] == 'unassigned'
    assert g.key_action('a', None, resolve)['status'] == 'needs-layout'
    assert calls == []
    assert g.key_action('a', '00000409', resolve)['status'] == 'unknown'
    monkeypatch.setitem(g.KEYBOARD_DEFAULTS, (1004, ('ctrl', 'shift')),
                        {'action': 'Fixture action', 'source': 'fixture'})
    assert g.key_action({'code': 'KeyA', 'modifiers': ['shift', 'ctrl']}, '00000409', resolve) == {'status': 'known', 'text': 'Fixture action'}
    assert g.key_action('a', '0000040c', resolve)['status'] == 'known'
    def unsupported(*args):
        raise ValueError('Unsupported key.')
    assert g.key_action('MediaPlayPause', '00000409', unsupported) == {'status': 'unsupported', 'text': 'Unsupported key.'}


@pytest.mark.parametrize('binding,layout', [(None, None), ([], None), ({}, None), ('a', 123), ('a', 'invalid'), ('x'*257, None)])
def test_malformed_lookup_rejected(binding, layout):
    with pytest.raises(ValueError):
        g.key_action(binding, layout, lambda *a: (1004, []))


@pytest.mark.parametrize('code,action', [
    ('KeyS','Ascend / Pitch up'),('KeyW','Descend / Pitch down'),('KeyA','Turn left / Roll left'),('KeyD','Turn right / Roll right'),
    ('KeyQ','Yaw left'),('KeyE','Yaw right'),('Space','Accelerate'),('ControlLeft','Decelerate'),
    ('KeyJ','Fire machine gun'),('KeyL','Fire missile / Weapon'),('KeyK','Change weapon / Next weapon'),('KeyI','Change weapon / Previous weapon'),
    ('Digit1','Standard missiles'),('Digit2','Special weapon 1'),('Digit3','Special weapon 2'),('KeyF','Camera control (mouse)'),
    ('Digit7','Camera up'),('Numpad8','Camera up'),('Digit8','Camera down'),('Numpad2','Camera down'),
    ('Digit9','Camera left'),('Numpad4','Camera left'),('Digit0','Camera right'),('Numpad6','Camera right'),
    ('KeyZ','Autopilot'),('KeyC','Autopilot'),('KeyR','Gear down / Gear up'),('KeyV','Change view'),
    ('KeyX','Deploy flares'),('KeyT','Change target'),('KeyM','Switch radar map'),
    ('ArrowUp','Order: Forward attack'),('ArrowDown','Order: Cover'),('ArrowLeft','Order: Disp. atk'),('ArrowRight','Order: SP weapons on/off')])
def test_every_supplied_keyboard_alternative(code, action):
    from app.keyboard import physical_binding
    result = g.key_action({'code': code, 'modifiers': []}, '0000040c', lambda binding, layout: physical_binding(binding))
    assert result == {'status':'known', 'text': action}


def test_azerty_typed_character_matches_qwerty_position_and_modifiers_are_exact():
    from tests.test_keyboard import api_factory, layouts
    from tests.test_windows import Fn
    from app.keyboard import LETTER_SCANS
    fake = api_factory()
    fake.MapVirtualKeyExW = Fn(lambda vk, mode, layout: LETTER_SCANS[ord({'A':'Q','Q':'A'}.get(chr(vk), chr(vk)) if layout == 0x040c else chr(vk))-65])
    resolver = layouts(fake).resolve
    assert g.key_action('a','0000040c',resolver)['text'] == 'Yaw left'
    assert g.key_action('a','00000409',resolver)['text'] == 'Turn left / Roll left'
    assert g.key_action({'code':'KeyQ','modifiers':[]},'0000040c',resolver)['text'] == 'Yaw left'
    assert g.key_action({'code':'KeyQ','modifiers':['shift']},'0000040c',resolver)['status'] == 'unknown'
    assert g.key_action('F24','0000040c',resolver)['text'] == 'No default action listed; set this action manually in game.'
@pytest.mark.parametrize('name,action', [
    ('A','Fire machine gun'),('B','Fire missile / Weapon'),('X','Change weapon'),('Y','Change target'),
    ('LT','Decelerate'),('RT','Accelerate'),('LB','Yaw left'),('RB','Yaw right'),
    ('BACK','Toggle radar map display'),('START','Pause menu on/off'),
    ('L3','Deploy flares with R3'),('R3','Change view; deploy flares with L3'),
    ('UP','Order: Forward attack'),('DOWN','Order: Cover'),('LEFT','Order: Disp. atk'),('RIGHT','Order: SP weapons on/off')])
def test_every_supplied_xbox_button_action(name, action):
    assert g.XBOX_DEFAULTS[name]['action'] == action
