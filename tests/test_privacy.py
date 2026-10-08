from pathlib import Path
from tools import privacy_check as p
import json
import hashlib
from types import SimpleNamespace
import pytest
import zipfile
import sys
import runpy


def fake_git(monkeypatch, entries=(), failed=False, identity=False):
    def run(args,**kw):
        if 'ls-files' in args:return SimpleNamespace(returncode=int(failed),stdout=b'\0'.join(str(v).encode() for v in entries)+b'\0')
        return SimpleNamespace(returncode=0 if identity else 1,stdout=b'ExamplePrivateIdentity' if identity else b'')
    monkeypatch.setattr(p.subprocess,'run',run)


def test_inventory_deduplicates_and_fails_closed(tmp_path,monkeypatch):
    fake_git(monkeypatch,['a.py','a.py','b.py'])
    assert p.inventory(tmp_path)==[Path('a.py'),Path('b.py')]
    fake_git(monkeypatch,failed=True)
    with pytest.raises(RuntimeError,match='inventory'):p.inventory(tmp_path)


def test_explicit_inventory_private_paths_symlinks_and_hash_bound_exception(tmp_path,monkeypatch):
    fake_git(monkeypatch,identity=True)
    monkeypatch.setattr(p.Path,'home',lambda:Path('/test/abc'))
    (tmp_path/'tools').mkdir();(tmp_path/'folder').mkdir()
    clean=tmp_path/'clean.py';clean.write_text('clean')
    personal='C:'+chr(92)+'Users'+chr(92)+'ExamplePrivateUser'
    (tmp_path/'path.py').write_text(personal)
    (tmp_path/'identity.py').write_text('ExamplePrivateIdentity')
    (tmp_path/'filename-ExamplePrivateIdentity.py').write_text('clean')
    (tmp_path/'unapproved.py').write_text(personal)
    paths=[Path(v) for v in ('.local/private.json','folder','missing.py','clean.py','path.py','identity.py','filename-ExamplePrivateIdentity.py','unapproved.py','symlink.py')]
    original=p.Path.is_symlink
    monkeypatch.setattr(p.Path,'is_symlink',lambda path:path.name=='symlink.py' or original(path))
    allow={'path.py':{'sha256':hashlib.sha256((tmp_path/'path.py').read_bytes()).hexdigest(),'categories':['personal Windows path']},
           'identity.py':{'sha256':hashlib.sha256((tmp_path/'identity.py').read_bytes()).hexdigest(),'categories':['current user identity/path']}}
    (tmp_path/'tools/privacy_upstream.json').write_text(json.dumps(allow))
    issues=p.audit(tmp_path,paths=paths)
    duplicate=tmp_path/'setups/xbox/path.py';duplicate.parent.mkdir(parents=True);duplicate.write_text(personal)
    assert p.audit(tmp_path,paths=[Path('setups/xbox/path.py')])==[]
    assert (Path('path.py'),'personal Windows path') not in issues
    assert (Path('identity.py'),'current user identity/path') in issues
    assert (Path('unapproved.py'),'personal Windows path') in issues
    assert (Path('symlink.py'),'symlink could expose external files') in issues
    assert any(path==paths[0] for path,label in issues)
    fake_git(monkeypatch,['clean.py']);assert p.audit(tmp_path)==[]
    monkeypatch.setattr(p.Path,'home',lambda:Path('/test/x'))
    assert p.audit(tmp_path,paths=[Path('clean.py')])==[]


def test_archive_inspection_members_size_and_corruption(tmp_path,monkeypatch):
    fake_git(monkeypatch)
    with zipfile.ZipFile(tmp_path/'data.zip','w') as archive:archive.writestr('ExamplePrivateMarker.py','ExamplePrivateMarker')
    issues=p.audit(tmp_path,['ExamplePrivateMarker'],paths=[Path('data.zip')])
    assert (Path('data.zip'),'current user identity/path') in issues
    (tmp_path/'bad.zip').write_text('broken')
    assert (Path('bad.zip'),'unreadable archive') in p.audit(tmp_path,paths=[Path('bad.zip')])
    class Archive:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def infolist(self):return [SimpleNamespace(file_size=300_000_000)]
    monkeypatch.setattr(p.zipfile,'ZipFile',lambda path:Archive())
    assert (Path('data.zip'),'archive too large for privacy inspection') in p.audit(tmp_path,paths=[Path('data.zip')])


def test_cli_self_test_exit_codes_and_safe_labels(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['privacy','--self-test'])
    assert p.main()==0
    monkeypatch.setattr(p.Path,'home',lambda:Path('/test/ExamplePrivateMarker'))
    assert p.safe_label(Path('folder/ExamplePrivateMarker/file.py'))=='folder/[private]/file.py'
    fake_git(monkeypatch,['clean.py']);(tmp_path/'clean.py').write_text('clean')
    monkeypatch.setattr(sys,'argv',['privacy','--root',str(tmp_path)])
    assert p.main()==0
    (tmp_path/'clean.py').write_text('ExamplePrivateMarker')
    assert p.main()==1
    assert 'ExamplePrivateMarker' not in capsys.readouterr().out
    monkeypatch.setattr(sys,'argv',['privacy','--self-test'])
    monkeypatch.delitem(sys.modules,'tools.privacy_check')
    with pytest.raises(SystemExit) as result:runpy.run_module('tools.privacy_check',run_name='__main__')
    assert result.value.code==0


def test_identity_matching_does_not_confuse_longer_upstream_names():
    marker='ExamplePrivateUser'
    assert not p.findings((marker+'m').encode(),(marker,))
    assert p.findings((marker+'_profile').encode(),(marker,))==['current user identity/path']
