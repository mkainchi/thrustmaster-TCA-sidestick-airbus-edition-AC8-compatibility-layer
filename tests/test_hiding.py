import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import subprocess
from app import hiding as h


def device(pid, present=True, gaming=True):
    return dict(deviceInstancePath='HID' + chr(92) + 'VID_044F&PID_' + pid + chr(92) + 'SYNTHETIC',
                present=present, gamingDevice=gaming)


class Driver:
    def __init__(self):
        self.hidden = set(); self.apps = set(); self.active = False; self.inverse = False
        self.devices = [device('0405'), device('0407'), device('1234'), device('0406', False)]
        self.failure = None

    def run(self, args, **kwargs):
        assert kwargs['capture_output'] and kwargs['timeout'] == 5
        command, *values = args[1:]
        if command == self.failure: raise OSError('private detail')
        output = ''
        if command == '--dev-gaming': output = json.dumps([dict(devices=self.devices)])
        elif command == '--dev-list': output = '\n'.join('--dev-hide "' + v + '"' for v in self.hidden)
        elif command == '--app-list': output = '\n'.join('--app-reg "' + str(Path(v)) + '"' for v in self.apps)
        elif command == '--cloak-state': output = '--cloak-on' if self.active else '--cloak-off'
        elif command == '--inv-state': output = '--inv-on' if self.inverse else '--inv-off'
        elif command == '--dev-hide':
            if values[0].upper() not in {v.upper() for v in self.hidden}: self.hidden.add(values[0])
        elif command == '--dev-unhide': self.hidden = {v for v in self.hidden if v.upper() != values[0].upper()}
        elif command == '--app-reg': self.apps.add(values[0])
        elif command == '--app-unreg': self.apps.discard(values[0])
        elif command == '--cloak-on': self.active = True
        elif command == '--cloak-off': self.active = False
        else: raise AssertionError(command)
        return SimpleNamespace(returncode=0, stdout=output)


def make(tmp_path, driver):
    return h.Hiding(tmp_path, ['C:/bridge/python.exe'], cli=Path('hidhide.exe'), runner=driver.run)


def test_only_supported_controllers_are_hidden_and_settings_restored(tmp_path):
    driver = Driver(); hiding = make(tmp_path, driver)
    hiding.start()
    assert driver.active and driver.hidden == {device('0405')['deviceInstancePath'], device('0407')['deviceInstancePath']}
    assert driver.apps == {str(Path('C:/bridge/python.exe'))}
    driver.devices.append(device('B10A'))
    hiding.combined()
    assert device('B10A')['deviceInstancePath'] in driver.hidden
    hiding.verify()
    hiding.close()
    assert not driver.active and not driver.hidden and not driver.apps
    assert not (tmp_path / 'hidhide-session.json').exists()


def test_existing_hiding_settings_and_later_unrelated_changes_survive(tmp_path):
    driver = Driver(); driver.active = True
    driver.hidden = {device('0405')['deviceInstancePath'], 'unrelated'}
    driver.apps = {'C:/bridge/python.exe', 'C:/other/tool.exe'}
    hiding = make(tmp_path, driver); hiding.start()
    driver.hidden.add('later'); driver.apps.add('C:/later/tool.exe')
    hiding.close()
    assert driver.active and driver.hidden == {device('0405')['deviceInstancePath'], 'unrelated', 'later'}
    assert driver.apps == {'C:/bridge/python.exe', 'C:/other/tool.exe', 'C:/later/tool.exe'}


@pytest.mark.parametrize('problem', ['inverse', 'steam', 'unrelated', 'missing', 'combined', 'tamper'])
def test_unsafe_or_incomplete_isolation_refuses_readiness(tmp_path, problem):
    driver = Driver()
    if problem == 'inverse': driver.inverse = True
    if problem == 'steam': driver.apps.add('C:/steam/Steam.exe')
    if problem == 'unrelated': driver.hidden.add('unrelated')
    if problem == 'missing': driver.devices = [device('0405')]
    hiding = make(tmp_path, driver)
    try:
        with pytest.raises(RuntimeError, match='HidHide'):
            hiding.start()
            if problem == 'combined': hiding.combined()
            if problem == 'tamper': driver.active = False; hiding.verify()
    finally: hiding.close()


def test_crash_journal_recovers_before_a_new_session(tmp_path):
    driver = Driver(); make(tmp_path, driver).start()
    assert (tmp_path / 'hidhide-session.json').exists()
    recovered = make(tmp_path, driver)
    assert not driver.active and not driver.hidden and not driver.apps
    recovered.start(); recovered.close()


def test_partial_failure_keeps_recovery_journal_and_redacts_errors(tmp_path):
    driver = Driver(); hiding = make(tmp_path, driver)
    driver.failure = '--cloak-on'
    with pytest.raises(RuntimeError, match='HidHide') as error: hiding.start()
    assert 'private detail' not in str(error.value)
    driver.failure = '--dev-unhide'
    with pytest.raises(RuntimeError): hiding.close()
    assert (tmp_path / 'hidhide-session.json').exists()
    driver.failure = None; make(tmp_path, driver)
    assert not driver.hidden and not driver.apps


def test_installation_supports_current_and_legacy_layouts(tmp_path, monkeypatch):
    monkeypatch.setenv('ProgramFiles', str(tmp_path))
    assert h.installation() is None
    legacy = tmp_path / 'Nefarius Software Solutions e.U./HidHide/x64/HidHideCLI.exe'
    legacy.parent.mkdir(parents=True); legacy.touch()
    assert h.installation() == legacy
    current = tmp_path / 'Nefarius Software Solutions/HidHide/HidHideCLI.exe'
    current.parent.mkdir(parents=True); current.touch()
    assert h.installation() == current
    monkeypatch.delenv('ProgramFiles')
    monkeypatch.setattr(h.Path, 'is_file', lambda p:False)
    assert h.installation() is None


def test_missing_busy_and_inverse_driver_prerequisites(tmp_path, monkeypatch):
    monkeypatch.setattr(h, 'installation', lambda:None)
    assert not h.ready()
    with pytest.raises(RuntimeError, match='Install HidHide'): h.Hiding(tmp_path, [])
    monkeypatch.setattr(h, 'installation', lambda:Path('hidhide.exe'))
    for result, expected in [('--inv-off', True), ('--inv-on', False)]:
        monkeypatch.setattr(h, 'command', lambda *a:result)
        assert h.ready() == expected
    def fail(*a): raise RuntimeError(h.ERROR)
    monkeypatch.setattr(h, 'command', fail)
    assert not h.ready()
    hiding = h.Hiding(tmp_path, [])
    hiding.close()


@pytest.mark.parametrize('problem', ['exit', 'timeout', 'oserror'])
def test_command_errors_are_bounded_and_never_expose_private_output(problem):
    def runner(*a, **kw):
        if problem == 'exit': return SimpleNamespace(returncode=1, stdout='private details')
        if problem == 'timeout': raise subprocess.TimeoutExpired(['private'], 5, output='private details')
        raise OSError('private details')
    with pytest.raises(RuntimeError) as error: h.command(Path('hidhide.exe'), '--inv-state', runner=runner)
    assert str(error.value) == h.ERROR


@pytest.mark.parametrize('output', ['invalid json', '[{}]', '[{"devices": null}]'])
def test_malformed_device_discovery_is_redacted(tmp_path, output):
    def runner(*a, **kw): return SimpleNamespace(returncode=0, stdout=output)
    hiding = h.Hiding(tmp_path, [], cli=Path('hidhide.exe'), runner=runner)
    with pytest.raises(RuntimeError) as error: hiding.devices(('0405',))
    assert str(error.value) == h.ERROR


def test_malformed_list_refuses_changes(tmp_path):
    hiding = h.Hiding(tmp_path, [], cli=Path('hidhide.exe'), runner=lambda *a, **kw:SimpleNamespace(returncode=0, stdout='private garbage'))
    with pytest.raises(RuntimeError) as error: hiding.start()
    assert str(error.value) == h.ERROR and not hiding.journal.exists()


@pytest.mark.parametrize('problem', ['inverse', 'device', 'app', 'steam'])
def test_loss_of_isolation_during_play_fails_closed(tmp_path, problem):
    driver = Driver(); hiding = make(tmp_path, driver); hiding.start()
    if problem == 'inverse': driver.inverse = True
    if problem == 'device': driver.hidden.clear()
    if problem == 'app': driver.apps.clear()
    if problem == 'steam': driver.apps.add('C:/steam/steam.exe')
    with pytest.raises(RuntimeError): hiding.verify()
    hiding.close()


def test_absent_stick_and_invalid_cloak_state_are_rejected(tmp_path):
    driver = Driver(); driver.devices = [device('0407')]
    hiding = make(tmp_path, driver)
    with pytest.raises(RuntimeError, match='both'): hiding.start()
    original = driver.run
    def runner(args, **kwargs):
        if args[1] == '--cloak-state': return SimpleNamespace(returncode=0, stdout='garbage')
        return original(args, **kwargs)
    hiding.runner = runner
    with pytest.raises(RuntimeError, match='normal'): hiding.start()


def test_existing_combined_and_non_gaming_interfaces_are_preserved(tmp_path):
    driver = Driver(); driver.active = True
    combined = device('B10A')['deviceInstancePath']
    driver.hidden.add(combined)
    driver.devices.extend([device('B10A'), device('0407', gaming=False)])
    hiding = make(tmp_path, driver); hiding.start(); hiding.combined(); hiding.close()
    assert driver.hidden == {combined} and driver.active


@pytest.mark.parametrize('data', ['bad json', '{}', 'null', '{"devices": "bad", "apps": [], "active": "--cloak-off"}',
                                 '{"devices": [], "apps": [1], "active": "--cloak-off"}',
                                 '{"devices": [], "apps": [], "active": "--invalid"}'])
def test_corrupt_recovery_journal_refuses_driver_changes(tmp_path, data):
    driver = Driver(); (tmp_path / 'hidhide-session.json').write_text(data)
    with pytest.raises(RuntimeError, match='HidHide'): make(tmp_path, driver)
    assert not driver.active and not driver.hidden and not driver.apps
    assert (tmp_path / 'hidhide-session.json').exists()


def test_existing_device_hiding_is_preserved_regardless_of_identifier_case(tmp_path):
    driver = Driver(); driver.active = True
    original = {device('0405')['deviceInstancePath'].lower(), device('B10A')['deviceInstancePath'].lower()}
    driver.hidden = original.copy(); driver.devices.append(device('B10A'))
    hiding = make(tmp_path, driver); hiding.start(); hiding.combined(); hiding.close()
    assert driver.hidden == original
