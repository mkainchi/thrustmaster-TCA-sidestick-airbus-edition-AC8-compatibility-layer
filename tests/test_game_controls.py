from app import game_controls as g
import pytest


def test_offline_choices_do_not_claim_unverified_defaults(monkeypatch):
    choices = g.xbox_choices()
    assert len(choices) == 16
    assert {'LT', 'RT'} <= {item['value'] for item in choices}
    assert all('Default unverified' in item['label'] for item in choices)
    monkeypatch.setitem(g.XBOX_DEFAULTS, 'A', {'action': 'Fixture action', 'source': 'fixture'})
    assert next(item for item in g.xbox_choices() if item['value'] == 'A')['label'] == 'A (Fixture action)'


def test_key_actions_resolve_layout_without_emitting_or_guessing(monkeypatch):
    calls = []
    def resolve(binding, layout):
        calls.append((binding, layout))
        return 1004, ['ctrl', 'shift']
    assert g.key_action('', None, resolve)['status'] == 'unassigned'
    assert g.key_action('a', None, resolve)['status'] == 'needs-layout'
    assert calls == []
    assert g.key_action('a', '00000409', resolve)['status'] == 'unknown'
    monkeypatch.setitem(g.KEYBOARD_DEFAULTS, ('00000409', 1004, ('ctrl', 'shift')),
                        {'action': 'Fixture action', 'source': 'fixture'})
    assert g.key_action({'code': 'KeyA', 'modifiers': ['shift', 'ctrl']}, '00000409', resolve) == {'status': 'known', 'text': 'Fixture action'}
    assert g.key_action('a', '0000040c', resolve)['status'] == 'unknown'
    def unsupported(*args):
        raise ValueError('Unsupported key.')
    assert g.key_action('MediaPlayPause', '00000409', unsupported) == {'status': 'unsupported', 'text': 'Unsupported key.'}


@pytest.mark.parametrize('binding,layout', [(None, None), ([], None), ({}, None), ('a', 123), ('a', 'invalid'), ('x'*257, None)])
def test_malformed_lookup_rejected(binding, layout):
    with pytest.raises(ValueError):
        g.key_action(binding, layout, lambda *a: (1004, []))
