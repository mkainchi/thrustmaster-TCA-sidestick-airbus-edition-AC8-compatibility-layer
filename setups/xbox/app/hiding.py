"""Session-owned HidHide changes; private identifiers never reach diagnostics."""
import json
import os
from pathlib import Path
import re
import subprocess

URL = 'https://docs.nefarius.at/projects/HidHide/Simple-Setup-Guide/'
ERROR = 'HidHide isolation failed. Close its configuration client, recheck dependencies and reconnect the controllers. Close Steam and the game before starting emulation.'


def installation():
    base = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
    for vendor in ('Nefarius Software Solutions', 'Nefarius Software Solutions e.U.'):
        for name in ('HidHideCLI.exe', 'x64/HidHideCLI.exe'):
            path = base / vendor / 'HidHide' / name
            if path.is_file():
                return path
    return None


def command(cli, *args, runner=subprocess.run):
    try:
        result = runner([str(cli), *args], capture_output=True, text=True, timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(ERROR)
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(ERROR) from None


def ready():
    cli = installation()
    if cli is None:
        return False
    try:
        return command(cli, '--inv-state') == '--inv-off'
    except RuntimeError:
        return False


class Hiding:
    def __init__(self, local, applications, cli=None, runner=subprocess.run):
        self.cli = cli if cli is not None else installation()
        if self.cli is None:
            raise RuntimeError('Install HidHide from Dependencies before emulating in any mode.')
        self.runner = runner
        self.journal = Path(local) / 'hidhide-session.json'
        self.applications = list(dict.fromkeys(str(Path(p)) for p in applications))
        self.state = None
        self.expected = set()
        if self.journal.exists():
            try:
                state = json.loads(self.journal.read_text(encoding='utf-8'))
                if state['active'] not in ('--cloak-on', '--cloak-off') or not all(
                        isinstance(state[key], list) and all(isinstance(value, str) and value for value in state[key])
                        for key in ('devices', 'apps')):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                raise RuntimeError('HidHide recovery data is invalid. Restore controller visibility in its configuration client before removing the private recovery journal.') from None
            self.state = state
            self.close()

    def call(self, *args):
        return command(self.cli, *args, runner=self.runner)

    def entries(self, kind):
        text = self.call('--' + kind + '-list')
        pattern = r'--' + ('dev-hide' if kind == 'dev' else 'app-reg') + r' "([^"\r\n]+)"'
        entries = [re.fullmatch(pattern, line) for line in text.splitlines()]
        if any(entry is None for entry in entries):
            raise RuntimeError(ERROR)
        return {entry[1].upper() if kind == 'dev' else entry[1] for entry in entries}

    def save(self):
        temporary = self.journal.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state), encoding='utf-8')
        temporary.replace(self.journal)

    def devices(self, pids):
        try:
            data = json.loads(self.call('--dev-gaming'))
            return {d['deviceInstancePath'].upper() for group in data for d in group['devices']
                    if d['present'] and d['gamingDevice'] and re.search(
                        r'VID_044F&PID_(' + '|'.join(pids) + r')(?:[&\\]|$)', d['deviceInstancePath'], re.I)}
        except (ValueError, KeyError, TypeError):
            raise RuntimeError(ERROR) from None

    def start(self):
        hidden = self.entries('dev')
        apps = self.entries('app')
        active = self.call('--cloak-state')
        if self.call('--inv-state') != '--inv-off' or active not in ('--cloak-on', '--cloak-off'):
            raise RuntimeError('HidHide requires normal application hiding. Turn inverse application cloak off.')
        if any(Path(p).name.lower() in ('steam.exe', 'steamwebhelper.exe') for p in apps):
            raise RuntimeError('Remove Steam from the HidHide Applications list before emulating.')
        stick = self.devices(('0405', '0406'))
        quadrant = self.devices(('0407',))
        devices = stick | quadrant
        if not stick or not quadrant:
            raise RuntimeError('HidHide must detect both supported TCA controllers. Reconnect them and retry.')
        if active == '--cloak-off' and hidden - devices:
            raise RuntimeError('HidHide has other hidden devices. Enable hiding yourself or clear unused entries before emulating.')
        self.state = dict(devices=list(devices - hidden), apps=[p for p in self.applications if p.lower() not in {a.lower() for a in apps}], active=active)
        self.save()
        for app in self.state['apps']:
            self.call('--app-reg', app)
        for device in self.state['devices']:
            self.call('--dev-hide', device)
        self.call('--cloak-on')
        self.expected = devices
        self.verify()

    def combined(self):
        devices = self.devices(('B10A',))
        if not devices:
            raise RuntimeError('HidHide cannot find TARGET Combined. Stop TARGET and reconnect both controllers.')
        additions = devices - self.entries('dev')
        self.state['devices'].extend(additions)
        self.save()
        for device in additions:
            self.call('--dev-hide', device)
        self.expected.update(devices)
        self.verify()

    def verify(self):
        apps = {p.lower() for p in self.entries('app')}
        if (self.call('--cloak-state') != '--cloak-on' or self.call('--inv-state') != '--inv-off'
                or not self.expected <= self.entries('dev') or not all(p.lower() in apps for p in self.applications)
                or any(Path(p).name.lower() in ('steam.exe', 'steamwebhelper.exe') for p in apps)):
            raise RuntimeError(ERROR)

    def close(self):
        if self.state is None:
            return
        for device in self.state['devices']:
            self.call('--dev-unhide', device)
        self.call(self.state['active'])
        for app in self.state['apps']:
            self.call('--app-unreg', app)
        self.journal.unlink()
        self.state = None
