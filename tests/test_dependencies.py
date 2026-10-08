from pathlib import Path
from app.dependencies import target_installation, status
from app import dependencies as d
import json
import hashlib
import pytest
from types import SimpleNamespace


def test_target_folder_requires_gui_plugin_and_headers(tmp_path):
    assert target_installation(tmp_path) is None
    for name in ('x64/TARGETGUI.exe', 'Plugins/sys.dll', 'scripts/target.tmh', 'scripts/defines.tmh', 'scripts/hid.tmh', 'scripts/sys.tmh'):
        p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'fixture')
    assert target_installation(tmp_path) == tmp_path / 'x64' / 'TARGETGUI.exe'


def test_only_selected_mode_dependencies_are_requested(tmp_path):
    items = status(tmp_path, 'xbox', '', candidates=[], probe=lambda: True, runtime=lambda: True, microsoft=lambda:True)
    assert {i['id'] for i in items} == {'runtime', 'microsoft', 'vigem'}
    assert all(i['ready'] for i in items)
    items = status(tmp_path, 'keyboard', '', candidates=[], probe=lambda: True, runtime=lambda: True, microsoft=lambda:True)
    assert {i['id'] for i in items} == {'runtime', 'microsoft', 'target'}
    assert not items[-1]['ready']


def test_integrity_requires_manifest_and_matching_files(tmp_path):
    assert not d.integrity(tmp_path)
    folder=tmp_path/'dependencies';folder.mkdir();manifest=folder/'manifest.json'
    manifest.write_text('{}');assert not d.integrity(tmp_path)
    manifest.write_text('bad');assert not d.integrity(tmp_path)
    manifest.write_text(json.dumps({'files':{}}));assert not d.integrity(tmp_path)
    manifest.write_text(json.dumps({'files':{'sample.bin':'wrong'}}));assert not d.integrity(tmp_path)
    (tmp_path/'sample.bin').write_bytes(b'fixture');assert not d.integrity(tmp_path)
    manifest.write_text(json.dumps({'files':{'sample.bin':hashlib.sha256(b'fixture').hexdigest()}}));assert d.integrity(tmp_path)


def test_microsoft_and_bus_probe_success_and_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(d,'load_dll',lambda name:object());assert d.microsoft_ready()
    def fail(name):raise OSError('unavailable')
    monkeypatch.setattr(d,'load_dll',fail);assert not d.microsoft_ready()
    closed=[]
    class FakePad:
        def __init__(self,path):pass
        def connect(self,create):assert create is False
        def close(self):closed.append(True)
    monkeypatch.setattr(d,'Pad',FakePad);assert d.bus_ready(tmp_path)
    def unavailable(self,create):raise RuntimeError('unavailable')
    FakePad.connect=unavailable;assert not d.bus_ready(tmp_path) and len(closed)==2


def test_registry_candidates_and_explicit_invalid_folder(monkeypatch,tmp_path):
    import winreg
    class Key:
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr(winreg,'OpenKey',lambda *a:Key())
    monkeypatch.setattr(winreg,'QueryValueEx',lambda *a:('registry-target',1))
    assert any(str(p)=='registry-target' for p in d.target_candidates())
    def unavailable(*a):raise OSError('missing')
    monkeypatch.setattr(winreg,'OpenKey',unavailable);assert len(d.target_candidates())==2
    for name in ('TARGETGUI.exe','Plugins/sys.dll','scripts/target.tmh','scripts/defines.tmh','scripts/hid.tmh','scripts/sys.tmh'):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
    assert target_installation(tmp_path)==tmp_path/'TARGETGUI.exe'
    monkeypatch.setattr(d,'target_candidates',lambda:[tmp_path]);monkeypatch.setattr(d,'integrity',lambda root:True)
    monkeypatch.setattr(d,'microsoft_ready',lambda:True);monkeypatch.setattr(d,'bus_ready',lambda root:True)
    items=status(tmp_path,'target-xbox','');assert all(i['ready'] for i in items)
    assert not status(tmp_path,'keyboard','bad-folder')[-1]['ready']
    monkeypatch.setattr(d,'bus_ready',lambda root:(_ for _ in ()).throw(OSError('unavailable')))
    assert not status(tmp_path,'xbox','')[-1]['ready']
    monkeypatch.setattr(d,'integrity',lambda root:False)
    assert not status(tmp_path,'xbox','')[-1]['ready']


def test_validated_target_path_is_returned(tmp_path):
    for name in ('x64/TARGETGUI.exe','Plugins/sys.dll','scripts/target.tmh','scripts/defines.tmh','scripts/hid.tmh','scripts/sys.tmh'):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
    items=status(tmp_path,'keyboard',str(tmp_path),candidates=[],runtime=lambda:True,microsoft=lambda:True)
    assert items[-1]['path']==str(tmp_path)
