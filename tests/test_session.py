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
                present=lambda:True, wallclock=time.time)
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
