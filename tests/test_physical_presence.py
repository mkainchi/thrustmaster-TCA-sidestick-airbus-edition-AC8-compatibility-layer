from types import SimpleNamespace
from app.windows import physical_present
from tests.test_windows import Fn
from app import windows as w
import ctypes as c
import pytest


def test_target_capture_does_not_hide_physical_presence_and_unplug_is_detected():
    identities = ['USB\\VID_044F&PID_0405', 'USB\\VID_044F&PID_0407']
    def enum(handle, index, ptr):
        ptr._obj.instance=index
        return index<len(identities)
    def property(handle, ptr, field, kind, buffer, size, required):
        raw=(identities[ptr._obj.instance]+'\x00').encode('utf-16-le')
        for i,b in enumerate(raw):buffer[i]=b
        return True
    api=SimpleNamespace(SetupDiGetClassDevsW=Fn(lambda *a:1),SetupDiEnumDeviceInfo=Fn(enum),
                        SetupDiGetDeviceRegistryPropertyW=Fn(property),SetupDiDestroyDeviceInfoList=Fn(lambda h:True))
    assert physical_present(api)
    identities.pop()
    assert not physical_present(api)


def test_presence_failure_cleanup_and_unrelated_property(monkeypatch):
    calls=[]
    api=SimpleNamespace(SetupDiGetClassDevsW=Fn(lambda *a:c.c_void_p(-1).value),SetupDiEnumDeviceInfo=Fn(lambda *a:False),
        SetupDiGetDeviceRegistryPropertyW=Fn(lambda *a:False),SetupDiDestroyDeviceInfoList=Fn(lambda h:calls.append(h)))
    monkeypatch.setattr(w,'load_dll',lambda name:api)
    with pytest.raises(RuntimeError):physical_present()
    api.SetupDiGetClassDevsW=Fn(lambda *a:1)
    api.SetupDiEnumDeviceInfo=Fn(lambda h,i,p:i<1)
    assert not physical_present(api) and calls==[1]
