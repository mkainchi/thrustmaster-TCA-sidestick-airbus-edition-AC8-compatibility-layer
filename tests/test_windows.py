import ctypes as c
from types import SimpleNamespace
import pytest
from app import windows as w
from app.windows import Joysticks, Caps, JoyInfo, Pad, XReport


class Fn:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *args): return self.fn(*args)


def test_native_input_decodes_ranges_buttons_and_diagonal_hat():
    def caps(index, pointer, size):
        obj = pointer._obj
        obj.mid, obj.pid, obj.axes, obj.buttons = 0x044f, (0x0405 if index == 0 else 0x0407), 4, 17
        for name in 'xyzruv':
            setattr(obj, name+'min', 0); setattr(obj, name+'max', 65535)
        return 0
    def read(index, pointer):
        obj = pointer._obj
        obj.x, obj.y, obj.z, obj.r, obj.u, obj.v = 65535, 0, 32767, 32767, 32767, 32767
        obj.buttons, obj.pov = 5, 4500
        return 0
    api = SimpleNamespace(joyGetNumDevs=Fn(lambda: 2), joyGetDevCapsW=Fn(caps), joyGetPosEx=Fn(read))
    device = Joysticks(api)
    api.joyConfigChanged=Fn(lambda flags:0)
    device.refresh()
    state = device.snapshot('xbox')
    assert state['stick']['buttons'] == [1, 3]
    assert state['stick']['hat'] == [1, 1]
    assert state['stick']['axes'][:2] == [1, -1]


def test_native_disconnect_is_actionable():
    api = SimpleNamespace(joyGetNumDevs=Fn(lambda: 0), joyGetDevCapsW=Fn(lambda *a: 1), joyGetPosEx=Fn(lambda *a: 1))
    with pytest.raises(RuntimeError, match='Connect'):
        Joysticks(api).snapshot('xbox')


def pad_api(bus=1, target=2, connect=0x20000000, add=0x20000000):
    calls=[]
    def call(name,result):
        def fn(*args):calls.append((name,args));return result
        return Fn(fn)
    api=SimpleNamespace(**{name:call(name,result) for name,result in {
        'vigem_alloc':bus,'vigem_target_x360_alloc':target,'vigem_connect':connect,'vigem_target_add':add,
        'vigem_free':None,'vigem_disconnect':None,'vigem_target_free':None,'vigem_target_remove':0x20000000,
        'vigem_target_x360_update':0x20000000}.items()})
    return api,calls


def test_virtual_pad_updates_neutralizes_and_frees_resources(monkeypatch):
    api,calls=pad_api();monkeypatch.setattr(c,'CDLL',lambda path:api)
    pad=Pad('fixture.dll');pad.connect()
    pad.update(dict(buttons=4096,lt=1,rt=0,lx=-1,ly=1,rx=0,ry=.5))
    values=next(args[-1] for name,args in calls if name=='vigem_target_x360_update')
    assert (values.buttons,values.lt,values.lx,values.ry)==(4096,255,-32767,16384)
    pad.close();pad.close()
    updates=[args[-1] for name,args in calls if name=='vigem_target_x360_update']
    assert updates[-1].buttons==0 and updates[-1].lt==0
    assert [name for name,args in calls].count('vigem_target_remove')==1


def test_pad_allocation_connect_add_and_update_failures():
    api,_=pad_api(bus=0)
    with pytest.raises(RuntimeError,match='allocate'):Pad('fixture',api)
    for kw in ({'connect':0},{'target':0},{'add':0}):
        api,calls=pad_api(**kw);pad=Pad('fixture',api)
        with pytest.raises(RuntimeError):pad.connect()
        pad.close();assert any(name=='vigem_free' for name,args in calls)
    api,_=pad_api();pad=Pad('fixture',api);pad.connect(create=False);pad.close()
    with pytest.raises(RuntimeError):Pad.check(0)
    Pad.check(0x20000000)


def test_raw_pov_center_missing_axes_and_disconnection():
    caps=Caps();caps.buttons=32
    api=SimpleNamespace(joyGetDevCapsW=Fn(lambda *a:0),joyGetPosEx=Fn(lambda i,p:setattr(p._obj,'pov',65535) or 0))
    reader=Joysticks(api)
    assert reader.read(0,caps)=={'axes':[0.]*6,'buttons':[],'hat':[0,0]}
    api.joyGetPosEx=Fn(lambda *a:1)
    with pytest.raises(RuntimeError,match='disconnected'):reader.read(0,caps)


def test_combined_descriptor_splits_physical_numbering_and_device_errors(monkeypatch):
    cap=Caps();cap.axes=4;cap.buttons=32;cap.name='Thrustmaster Combined'
    reader=Joysticks(SimpleNamespace(joyGetDevCapsW=Fn(lambda *a:0),joyGetPosEx=Fn(lambda *a:0)))
    monkeypatch.setattr(reader,'devices',lambda:[(0,cap)])
    monkeypatch.setattr(reader,'read',lambda *a:{'axes':[0.]*6,'buttons':[1,16,17,32],'hat':[1,0]})
    data=reader.snapshot('target-xbox');assert data['stick']['buttons']==[1,16] and data['quadrant']['buttons']==[1,16]
    cap.name='Generic';cap.mid=0x044f;cap.pid=0xb10a
    assert reader.snapshot('target-xbox')['quadrant']['hat']==[0,0]
    cap.mid=0
    with pytest.raises(RuntimeError,match='Waiting'):reader.snapshot('target-xbox')
    cap.mid=0x044f;cap.pid=0x0405
    with pytest.raises(RuntimeError,match='Connect'):reader.snapshot('xbox')
    def getcap(i,p,size):
        p._obj.mid=0;return 1 if i==0 else 0
    api=SimpleNamespace(joyGetNumDevs=Fn(lambda:2),joyGetDevCapsW=Fn(getcap),joyGetPosEx=Fn(lambda *a:1))
    monkeypatch.setattr(c,'WinDLL',lambda name:api)
    assert w.load_dll('test') is api
    assert Joysticks().devices()==[]


def test_xinput_reads_only_connected_slots(monkeypatch):
    def read(i,p):p._obj.report.buttons=i;return 0 if i==1 else 1167
    api=SimpleNamespace(XInputGetState=Fn(read))
    assert w.xinput(api)[1].buttons==1
    monkeypatch.setattr(w,'load_dll',lambda name:api)
    assert set(w.xinput())=={1}
def test_failed_neutral_write_still_removes_controller():
    from app.windows import Pad
    api, calls = pad_api()
    pad = Pad('unused', api=api); pad.connect()
    def fail(*args): raise OSError('disconnected')
    api.vigem_target_x360_update = Fn(fail)
    with pytest.raises(OSError): pad.close()
    assert any(name == 'vigem_target_remove' for name, args in calls)


def test_named_mutex_owns_across_packages_and_releases_on_failure(monkeypatch):
    calls=[]
    api=SimpleNamespace(CreateMutexW=Fn(lambda *a:1),WaitForSingleObject=Fn(lambda *a:0),
                        ReleaseMutex=Fn(lambda h:calls.append('release')),CloseHandle=Fn(lambda h:calls.append('close')))
    monkeypatch.setattr(w,'load_dll',lambda name:api)
    with w.controller_guard(): pass
    assert calls==['release','close']
    api.WaitForSingleObject=Fn(lambda *a:128)
    with pytest.raises(ValueError):
        with w.controller_guard(api):raise ValueError('body failed')
    assert calls[-2:]==['release','close']
    api.WaitForSingleObject=Fn(lambda *a:258)
    with pytest.raises(RuntimeError,match='Another'):
        with w.controller_guard(api):pass
    assert calls[-1]=='close'
    api.CreateMutexW=Fn(lambda *a:0)
    with pytest.raises(RuntimeError,match='reserve'):
        with w.controller_guard(api):pass
