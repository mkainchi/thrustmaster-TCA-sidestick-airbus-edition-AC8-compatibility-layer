"""One owned session, verified startup and cooperative cleanup."""
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from .dependencies import status, target_installation
from .keyboard import WindowsLayouts
from .model import Store, validate, report, ThrottleSelector
from .target import generate
from .windows import Joysticks, Pad, xinput, physical_present, controller_guard


def wait_for(predicate, message, timeout=20, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while not predicate():
        if clock() >= deadline:
            raise RuntimeError(message)
        sleep(0.1)


def request_stop(local):
    local = Path(local)
    session = local / 'session.json'
    if not session.exists():
        return False
    nonce = json.loads(session.read_text())['nonce']
    if not isinstance(nonce, str) or not re.fullmatch('[a-z0-9]+', nonce):
        raise ValueError('Invalid local session metadata.')
    (local / f'{nonce}.stop').touch()
    return True


def file_lock(handle, release=False):
    import msvcrt
    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)


def run(root, seconds=None, guard=controller_guard, **boundaries):
    with guard():
        return owned_run(root, seconds, **boundaries)


def owned_run(root, seconds=None, inputs=None, pad_factory=Pad, detect=status, launch=subprocess.Popen,
        read_xinput=xinput, clock=time.monotonic, sleep=time.sleep, lock=file_lock, layouts_factory=WindowsLayouts,
        present=physical_present, wallclock=time.time, expected_mode=None):
    store = Store(root)
    saved = store.load()
    mode = saved['preferred_mode']
    if mode is None:
        raise ValueError('Run configure.cmd and save a preferred mode first.')
    if expected_mode is not None and mode != expected_mode:
        raise ValueError('This package uses a different mode. Run its configure.cmd and save that mode first.')
    cfg = validate(mode, saved['profiles'][mode])
    prerequisites = detect(root, mode, saved['target_path'])
    if not all(item['ready'] for item in prerequisites):
        raise RuntimeError('A required dependency is missing or unhealthy. Run configure.cmd and recheck dependencies.')
    inputs = inputs if inputs is not None else Joysticks()
    local = store.local
    local.mkdir(parents=True, exist_ok=True)
    handle = (local / 'session.lock').open('a+b')
    handle.write(b'0'); handle.flush()
    try:
        lock(handle)
    except OSError:
        handle.close()
        raise RuntimeError('Emulation is already running. Use emulate.cmd --stop first.') from None
    nonce = secrets.token_hex(16)
    stop = local / f'{nonce}.stop'
    ready = local / f'{nonce}.ready'
    pad, process = None, None
    metadata = local / 'session.json'
    cleanup_failed = False
    try:
        if metadata.exists():
            cleanup_failed = True
            try:
                inputs.snapshot('xbox')
            except RuntimeError:
                raise RuntimeError('The previous TARGET session did not stop cleanly. Click Stop in TARGET, reconnect both devices, then retry.') from None
            cleanup_failed = False
        metadata.write_text(json.dumps({'nonce': nonce, 'mode': mode}))
        if mode in ('keyboard', 'target-xbox'):
            # Check physical devices and select Pilot/Copilot before TARGET captures them.
            inputs.snapshot('xbox')
            copilot = any(cap.pid == 0x0406 for _, cap in inputs.devices())
            resolver = layouts_factory().resolve if mode == 'keyboard' else None
            script = local / f'{mode}.tmc'
            script.write_text(generate(mode, cfg, local, nonce, resolver, copilot), encoding='utf-8')
            folder = next(item['path'] for item in prerequisites if item['id'] == 'target')
            process = launch([str(target_installation(folder)), '-r', str(script.resolve())], cwd=folder)
            wait_for(lambda: ready.exists() and ready.read_text() == nonce,
                     'TARGET did not become ready. Inspect its compile/filter error and stop that profile before retrying.',
                     clock=clock, sleep=sleep)
        if mode != 'keyboard':
            if mode == 'target-xbox':
                def combined_ready():
                    try:
                        inputs.refresh()
                        inputs.snapshot(mode)
                        return True
                    except RuntimeError:
                        return False
                wait_for(combined_ready, 'TARGET Combined did not appear with 4 axes and 32 buttons. Stop the profile and recheck its descriptor.',
                         clock=clock, sleep=sleep)
            else:
                initial = inputs.snapshot(mode)
                throttle_selector = ThrottleSelector()
                throttle_selector.read(initial['stick']['axes'][2], initial['quadrant']['axes'][cfg['axes']['throttle']])
            before = set(read_xinput())
            if len(before) == 4:
                raise RuntimeError('All four XInput slots are occupied. Disconnect an unused controller and retry.')
            pad = pad_factory(Path(root) / 'dependencies' / 'ViGEmClient.dll')
            pad.connect()
            wait_for(lambda: len(set(read_xinput()) - before) == 1,
                     'The Xbox controller did not appear in XInput. Recheck ViGEmBus and free controller slots.', clock=clock, sleep=sleep)
        print('READY. Keep this window open. Ctrl+C or emulate.cmd --stop ends this session.')
        deadline = None if seconds is None else clock() + seconds
        next_presence_check = 0
        while not stop.exists() and (deadline is None or clock() < deadline):
            if clock() >= next_presence_check:
                if not present():
                    raise RuntimeError('A TCA device disconnected. Controls released; reconnect both devices and restart.')
                next_presence_check = clock() + 1
            if mode == 'keyboard':
                if not ready.exists() or wallclock() - ready.stat().st_mtime > 2:
                    raise RuntimeError('TARGET stopped unexpectedly. Recheck the profile before restarting.')
            else:
                snapshot = inputs.snapshot(mode)
                throttle = throttle_selector.read(snapshot['stick']['axes'][2], snapshot['quadrant']['axes'][cfg['axes']['throttle']]) if mode == 'xbox' else None
                pad.update(report(snapshot, cfg, throttle=throttle))
            sleep(1 / cfg['poll_hz'])
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            try:
                if pad is not None:
                    pad.close()
            finally:
                if process is not None:
                    try:
                        stop.touch()
                        wait_for(lambda: ready.exists() and ready.read_text() == '0',
                                 'TARGET did not acknowledge stop. Click Stop in TARGET before using other controllers.',
                                 timeout=5, clock=clock, sleep=sleep)
                    except (RuntimeError, OSError):
                        cleanup_failed = True
                        if failed:
                            print('TARGET stop was not confirmed. Click Stop in TARGET and reconnect both devices before retrying.', file=sys.stderr)
                        else:
                            raise
        finally:
            if not cleanup_failed:
                metadata.unlink(missing_ok=True)
            try:
                lock(handle, release=True)
            finally:
                handle.close()
