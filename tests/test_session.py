import json
import pytest
from app.session import request_stop, wait_for
from app import session as s
from app.model import Store, defaults
from types import SimpleNamespace
from contextlib import nullcontext
import os
import time


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, value): self.now += value


class Inputs:
    def __init__(self, failure=None): self.failure = failure; self.modes = []
    def devices(self): return [(0, SimpleNamespace(pid=0x0406))]
    def refresh(self): pass
    def snapshot(self, mode):
        self.modes.append(mode)
        if self.failure: raise RuntimeError(self.failure)
        return {device: {'axes':[0.]*6,'buttons':[],'hat':[0,0]} for device in ('stick','quadrant')}


class Pad:
    def __init__(self): self.connected = False; self.closed = False; self.values = []
    def connect(self): self.connected = True
    def update(self, value): self.values.append(value)
    def close(self): self.closed = True


class Hiding:
    def start(self): pass
    def combined(self): pass
    def verify(self): pass
    def close(self): pass


def harness(root, mode='xbox', acknowledge=True, ready=True):
    cfg = defaults(mode)
    if mode == 'keyboard': cfg['layout'] = '00000409'
    Store(root).save(mode, cfg, '')
    ticks = Clock(); pad = Pad(); inputs = Inputs(); locks = []
    def launch(args, cwd):
        text = __import__('pathlib').Path(args[-1]).read_text()
        nonce = json.loads((root/'.local/session.json').read_text())['nonce']
        signal = root/'.local'/f'{nonce}.ready'
        if ready: signal.write_text(nonce)
        assert 'ProfileReady();' in text and args[1] == '-r'
        return object()
    def sleep(value):
        ticks.sleep(value)
        if acknowledge:
            for stop in (root/'.local').glob('*.stop'): stop.with_suffix('.ready').write_text('0')
    args = dict(guard=nullcontext, inputs=inputs, pad_factory=lambda path:pad, detect=lambda *a:[{'id':'target','path':str(root),'ready':True}],
                launch=launch, read_xinput=lambda:{0:None} if pad.connected else {}, clock=ticks, sleep=sleep,
                lock=lambda h,release=False:locks.append(release), layouts_factory=lambda:SimpleNamespace(resolve=lambda *a:(1004,[])),
                present=lambda:True, wallclock=time.time, hiding_factory=lambda *a:Hiding())
    return args, pad, inputs, locks


@pytest.mark.parametrize('mode',['keyboard','xbox','target-xbox'])
def test_owned_lifecycle_neutral_cleanup_and_timed_stop(tmp_path, mode, monkeypatch):
    args,pad,inputs,locks=harness(tmp_path,mode)
    monkeypatch.setattr(s,'target_installation',lambda folder:'targetgui.exe')
    s.run(tmp_path, seconds=.03, **args)
    assert locks == [False,True] and not (tmp_path/'.local/session.json').exists()
    assert pad.closed == (mode != 'keyboard')
    if mode != 'keyboard': assert pad.values and pad.values[0]['buttons'] == 0
    if mode == 'target-xbox': assert 'target-xbox' in inputs.modes


def test_missing_configuration_dependency_and_competing_session(tmp_path):
    with pytest.raises(ValueError,match='configure'):s.run(tmp_path,guard=nullcontext)
    args,pad,inputs,locks=harness(tmp_path)
    with pytest.raises(ValueError,match='different mode'):s.run(tmp_path,expected_mode='keyboard',**args)
    args['detect']=lambda *a:[{'ready':False}]
    with pytest.raises(RuntimeError,match='dependency'):s.run(tmp_path,**args)
    args['detect']=lambda *a:[]
    def locked(*a,**kw): raise OSError('owned')
    args['lock']=locked
    with pytest.raises(RuntimeError,match='already'):s.run(tmp_path,**args)


def test_default_native_inputs_stop_file_and_stale_recovery(tmp_path, monkeypatch):
    args,pad,inputs,locks=harness(tmp_path)
    monkeypatch.setattr(s,'Joysticks',lambda:inputs); args['inputs']=None
    (tmp_path/'.local/session.json').write_text('{}')
    original=args['sleep']
    def sleep(value):
        original(value)
        request_stop(tmp_path/'.local')
    args['sleep']=sleep
    s.run(tmp_path,**args)
    assert inputs.modes[0]=='xbox' and pad.closed
    args,pad,inputs,locks=harness(tmp_path)
    (tmp_path/'.local/session.json').write_text('{}');inputs.failure='filtered'
    with pytest.raises(RuntimeError,match='previous TARGET'):s.run(tmp_path,**args)


@pytest.mark.parametrize('failure',['disconnect','slots','xinput','connect','update'])
def test_xbox_startup_and_runtime_failures_always_cleanup(tmp_path,failure):
    args,pad,inputs,locks=harness(tmp_path)
    if failure=='disconnect':args['present']=lambda:False
    if failure=='slots':args['read_xinput']=lambda:dict.fromkeys(range(4))
    if failure=='xinput':args['read_xinput']=lambda:{}
    if failure=='connect':pad.connect=lambda:(_ for _ in ()).throw(RuntimeError('connect failed'))
    if failure=='update':pad.update=lambda value:(_ for _ in ()).throw(RuntimeError('update failed'))
    with pytest.raises(RuntimeError):s.run(tmp_path,seconds=.01,**args)
    assert locks==[False,True] and not (tmp_path/'.local/session.json').exists()
    assert pad.closed == (failure!='slots')


@pytest.mark.parametrize('problem',['timeout','missing','stale','stop','pad-close'])
def test_target_errors_preserve_startup_error_and_attempt_stop(tmp_path,problem,monkeypatch,capsys):
    args,pad,inputs,locks=harness(tmp_path,'keyboard' if problem!='pad-close' else 'target-xbox',acknowledge=False,ready=problem!='timeout')
    monkeypatch.setattr(s,'target_installation',lambda folder:'targetgui.exe')
    if problem=='missing':
        args['present']=lambda:next((p.unlink() or True for p in (tmp_path/'.local').glob('*.ready')),True)
    if problem=='stale':args['wallclock']=lambda:time.time()+10
    if problem=='pad-close':pad.close=lambda:(_ for _ in ()).throw(OSError('close failed'))
    with pytest.raises((RuntimeError,OSError)) as result:s.run(tmp_path,seconds=.01,**args)
    assert locks==[False,True] and (tmp_path/'.local/session.json').exists()
    if problem=='timeout':
        assert 'did not become ready' in str(result.value)
        assert 'stop was not confirmed' in capsys.readouterr().err
    if problem=='stop':assert 'acknowledge stop' in str(result.value)


def test_pad_close_failure_still_stops_target_and_unlock_failure_closes_handle(tmp_path,monkeypatch):
    args,pad,inputs,locks=harness(tmp_path,'target-xbox')
    monkeypatch.setattr(s,'target_installation',lambda folder:'targetgui.exe')
    snapshot=inputs.snapshot;attempts=[]
    def delayed(mode):
        if mode=='target-xbox' and not attempts:
            attempts.append(True);raise RuntimeError('not yet enumerated')
        return snapshot(mode)
    inputs.snapshot=delayed
    pad.close=lambda:(_ for _ in ()).throw(OSError('close failed'))
    with pytest.raises(OSError):s.run(tmp_path,seconds=.01,**args)
    assert any(p.read_text()=='0' for p in (tmp_path/'.local').glob('*.ready'))
    args,pad,inputs,locks=harness(tmp_path)
    handles=[]
    def lock(handle,release=False):
        handles.append(handle)
        if release: raise OSError('unlock')
    args['lock']=lock
    with pytest.raises(OSError):s.run(tmp_path,seconds=.01,**args)
    assert handles[-1].closed


def test_windows_byte_lock_and_wait_retry(tmp_path,monkeypatch):
    import msvcrt
    calls=[];monkeypatch.setattr(msvcrt,'locking',lambda *a:calls.append(a))
    with (tmp_path/'lock').open('wb') as handle:
        s.file_lock(handle);s.file_lock(handle,True)
    assert calls[0][1]==msvcrt.LK_NBLCK and calls[1][1]==msvcrt.LK_UNLCK
    ticks=Clock()
    wait_for(lambda:ticks.now>.1,'timeout',clock=ticks,sleep=ticks.sleep)


def test_stop_only_signals_a_valid_owned_session(tmp_path):
    local = tmp_path / '.local'; local.mkdir()
    assert request_stop(local) is False
    (local / 'session.json').write_text(json.dumps({'nonce': 'abc123'}))
    assert request_stop(local) is True
    assert (local / 'abc123.stop').exists()
    (local / 'session.json').write_text(json.dumps({'nonce': '../unsafe'}))
    with pytest.raises(ValueError): request_stop(local)


def test_readiness_timeout_is_actionable():
    ticks = iter([0, 1, 2])
    with pytest.raises(RuntimeError, match='ready'):
        wait_for(lambda: False, 'TARGET did not become ready.', timeout=1, clock=lambda: next(ticks), sleep=lambda _: None)
def test_direct_session_uses_last_moved_throttle_and_resets_ownership(tmp_path):
    args, pad, inputs, _ = harness(tmp_path)
    readings = iter([(0, 1), (0, 1), (-.9, .99), (-.9, -.5)])
    def snapshot(mode):
        stick, quadrant = next(readings)
        return {'stick': {'axes': [0, 0, stick, 0, 0, 0], 'buttons': [], 'hat': [0, 0]},
                'quadrant': {'axes': [quadrant, 0, 0, 0, 0, 0], 'buttons': [], 'hat': [0, 0]}}
    # Startup presence read precedes the three emulation samples.
    inputs.snapshot = snapshot
    s.run(tmp_path, seconds=.024, **args)
    assert pad.values[0]['lt'] == 1
    assert pad.values[1]['rt'] == pytest.approx(.83 / .93)
    assert pad.values[2]['rt'] == pytest.approx(.43 / .93)
    args, pad, inputs, _ = harness(tmp_path)
    inputs.snapshot = lambda mode: {'stick': {'axes': [0, 0, -1, 0, 0, 0], 'buttons': [], 'hat': [0, 0]},
                                   'quadrant': {'axes': [1, 0, 0, 0, 0, 0], 'buttons': [], 'hat': [0, 0]}}
    s.run(tmp_path, seconds=.008, **args)
    assert pad.values[0]['lt'] == 1


@pytest.mark.parametrize('mode', ['keyboard', 'xbox', 'target-xbox'])
def test_source_isolation_precedes_input_and_cleans_up_after_output(tmp_path, mode, monkeypatch):
    args, pad, inputs, locks = harness(tmp_path, mode)
    events = []
    class Isolation(Hiding):
        def start(self): events.append('hide')
        def combined(self): events.append('combined')
        def verify(self): events.append('verify')
        def close(self):
            assert pad.closed == (mode != 'keyboard')
            events.append('restore')
    def factory(local, applications):
        assert local == tmp_path / '.local'
        assert applications[0] == s.sys.executable
        return Isolation()
    args['hiding_factory'] = factory
    snapshot = inputs.snapshot
    def read(mode):
        assert 'hide' in events
        return snapshot(mode)
    inputs.snapshot = read
    monkeypatch.setattr(s, 'target_installation', lambda folder: 'targetgui.exe')
    s.run(tmp_path, seconds=.01, **args)
    assert events[0] == 'hide' and events[-1] == 'restore' and 'verify' in events
    assert ('combined' in events) == (mode != 'xbox')


def test_isolation_failure_prevents_output_and_restore_failure_keeps_recovery(tmp_path):
    args, pad, inputs, locks = harness(tmp_path)
    class Isolation(Hiding):
        def start(self): raise RuntimeError('HidHide failed')
    args['hiding_factory'] = lambda *a:Isolation()
    with pytest.raises(RuntimeError, match='HidHide'): s.run(tmp_path, **args)
    assert not pad.connected and locks == [False, True]
    args, pad, inputs, locks = harness(tmp_path)
    class BrokenRestore(Hiding):
        def close(self): raise RuntimeError('HidHide restore failed')
    args['hiding_factory'] = lambda *a:BrokenRestore()
    with pytest.raises(RuntimeError, match='restore'): s.run(tmp_path, seconds=.01, **args)
    assert pad.closed and locks == [False, True] and (tmp_path / '.local/session.json').exists()


def test_primary_error_survives_hidhide_cleanup_failure(tmp_path, capsys):
    args, pad, inputs, locks = harness(tmp_path)
    class Isolation(Hiding):
        def verify(self): raise RuntimeError('isolation lost')
        def close(self): raise RuntimeError('restore failed')
    args['hiding_factory'] = lambda *a:Isolation()
    with pytest.raises(RuntimeError, match='isolation lost'): s.run(tmp_path, **args)
    assert pad.closed and locks == [False, True]
    assert 'HidHide restoration failed' in capsys.readouterr().err


def test_unavailable_hiding_client_releases_ownership_without_starting_output(tmp_path):
    args, pad, inputs, locks = harness(tmp_path)
    def unavailable(*a): raise RuntimeError('HidHide unavailable')
    args['hiding_factory'] = unavailable
    with pytest.raises(RuntimeError, match='unavailable'): s.run(tmp_path, **args)
    assert locks == [False, True] and not pad.connected and not inputs.modes
    assert not (tmp_path / '.local/session.json').exists()


def test_hidhide_subprocess_checks_do_not_interrupt_the_input_loop(tmp_path):
    args, pad, inputs, locks = harness(tmp_path)
    checks = []
    class Isolation(Hiding):
        def verify(self): checks.append(True)
    args['hiding_factory'] = lambda *a:Isolation()
    s.run(tmp_path, seconds=1.05, **args)
    assert len(checks) == 1
    assert len(pad.values) > 100


@pytest.mark.parametrize('mode', ['keyboard', 'target-xbox'])
def test_target_isolation_waits_for_late_combined_enumeration(tmp_path, mode, monkeypatch):
    args, pad, inputs, locks = harness(tmp_path, mode)
    attempts = []
    for name in ('Interpreter.exe', 'TmService.exe'): (tmp_path / name).touch()
    class Isolation(Hiding):
        def combined(self):
            attempts.append(True)
            if len(attempts) == 1: raise RuntimeError('not yet enumerated')
    def factory(local, applications):
        assert str(tmp_path / 'Interpreter.exe') in applications
        assert str(tmp_path / 'TmService.exe') in applications
        return Isolation()
    args['hiding_factory'] = factory
    monkeypatch.setattr(s, 'target_installation', lambda folder:'targetgui.exe')
    s.run(tmp_path, seconds=.01, **args)
    assert len(attempts) == 2
