"""Read-only prerequisite discovery. Never installs drivers or accepts licenses."""
import hashlib
import json
import os
from pathlib import Path
from .windows import Pad, load_dll

TARGET_URL = 'https://support.thrustmaster.com/en/product/tca-sidestick-airbus-edition-en/'
VIGEM_URL = 'https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0'
MICROSOFT_URL = 'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist'


def target_installation(folder):
    folder = Path(folder)
    for gui in (folder / 'x64' / 'TARGETGUI.exe', folder / 'TARGETGUI.exe'):
        if gui.is_file() and all((folder / p).is_file() for p in (
                'Plugins/sys.dll', 'scripts/target.tmh', 'scripts/defines.tmh', 'scripts/hid.tmh', 'scripts/sys.tmh')):
            return gui
    return None


def target_candidates():
    paths = [Path(os.environ.get(key, fallback)) / 'Thrustmaster' / 'TARGET'
             for key, fallback in (('ProgramFiles(x86)', r'C:\Program Files (x86)'), ('ProgramFiles', r'C:\Program Files'))]
    import winreg
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Thrustmaster\TARGET', 0, winreg.KEY_READ | view) as key:
                    paths.append(Path(winreg.QueryValueEx(key, 'InstallDir')[0]))
            except OSError:
                pass
    return paths


def integrity(root):
    root = Path(root)
    try:
        files = json.loads((root / 'dependencies' / 'manifest.json').read_text())['files']
        return bool(files) and all((root / name).is_file() and hashlib.sha256((root / name).read_bytes()).hexdigest() == checksum
                                   for name, checksum in files.items())
    except (OSError, ValueError, KeyError):
        return False


def microsoft_ready():
    try:
        load_dll('vcruntime140.dll')
        load_dll('vcruntime140_1.dll')
        return True
    except OSError:
        return False


def bus_ready(root):
    pad = Pad(Path(root) / 'dependencies' / 'ViGEmClient.dll')
    try:
        pad.connect(create=False)
        return True
    except RuntimeError:
        return False
    finally:
        pad.close()


def status(root, mode, configured, candidates=None, probe=None, runtime=None, microsoft=None):
    runtime = runtime if runtime is not None else lambda: integrity(root)
    microsoft = microsoft if microsoft is not None else microsoft_ready
    items = [dict(id='runtime', label='Bundled runtime', ready=runtime(), path='', url='',
                  remedy='Restore the bundle from a verified release if files are missing or changed.'),
             dict(id='microsoft', label='Microsoft Visual C++ x64 runtime', ready=microsoft(), path='', url=MICROSOFT_URL,
                  remedy='Download and install the official x64 runtime, then recheck.')]
    if mode in ('keyboard', 'target-xbox'):
        paths = [Path(configured)] if configured else (target_candidates() if candidates is None else candidates)
        found = next((p for p in paths if target_installation(p)), None)
        items.append(dict(id='target', label='Thrustmaster TARGET', ready=found is not None,
                          path=str(found) if found is not None else configured, url=TARGET_URL,
                          remedy='Choose the installation folder containing Plugins, scripts and TARGETGUI, or install TARGET.'))
    if mode in ('xbox', 'target-xbox'):
        try:
            ready = items[0]['ready'] and (probe() if probe is not None else bus_ready(root))
        except (OSError, RuntimeError):
            ready = False
        items.append(dict(id='vigem', label='ViGEmBus driver', ready=ready, path='', url=VIGEM_URL,
                          remedy='Install the official 1.22.0 driver, restart Windows if requested, then recheck.'))
    return items
