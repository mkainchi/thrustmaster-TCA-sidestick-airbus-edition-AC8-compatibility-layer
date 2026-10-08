import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
import zipfile
import pytest
from tools import distribution as d
from tools import privacy_check as p


def repository(root, monkeypatch):
    files = {name:b'original' for name in (*d.ROOT_FILES,*d.APP_FILES,*d.DOC_FILES)}
    files.update({'runtime/python.exe':b'python','runtime/LICENSE.txt':b'PSF notice',
                  'dependencies/ViGEmClient.dll':b'client','dependencies/licenses/vigemclient-LICENSE.txt':b'MIT notice'})
    for name,data in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    manifest={'version':1,'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items() if name.startswith(('runtime/','dependencies/'))},
              'components':[{'name':'cpython','version':'3','license':'PSF-2.0','origin':'https://example.invalid/python','notice':'runtime/LICENSE.txt','files':['runtime/python.exe','runtime/LICENSE.txt']},
                            {'name':'vigemclient','version':'1','license':'MIT','origin':'https://example.invalid/client','notice':'dependencies/licenses/vigemclient-LICENSE.txt','files':['dependencies/ViGEmClient.dll','dependencies/licenses/vigemclient-LICENSE.txt']}]}
    (root/'dependencies/manifest.json').write_text(json.dumps(manifest))
    skill=root/'.agents/skills/example';skill.mkdir(parents=True)
    for name in ('LICENSE','SKILL.md','PreservedUpstream.txt'):(skill/name).write_text('MIT upstream')
    locked=[{'name':'example','commit':'a'*40,'license':'MIT','files':{name:d.digest(skill/name) for name in ('LICENSE','SKILL.md','PreservedUpstream.txt')}}]
    (root/'.agents/skills.lock.json').write_text(json.dumps(locked))
    monkeypatch.setattr(d,'inventory',lambda r:[f.relative_to(r) for f in r.rglob('*') if f.is_file() and not p.is_private(f.relative_to(r))])
    monkeypatch.setattr(p.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1,stdout=b''))
    return manifest,locked


def test_manifest_paths_hashes_notices_and_unresolved_permission(tmp_path,monkeypatch):
    manifest,_=repository(tmp_path,monkeypatch)
    assert d.locked_files(tmp_path)==manifest
    for name in ('../unsafe','/unsafe','C:/unsafe','bad\\name',''):
        with pytest.raises(ValueError):d.safe_relative(name)
    assert d.safe_relative('runtime/python.exe')==Path('runtime/python.exe')
    path=tmp_path/'dependencies/manifest.json'
    for changed in ({},dict(manifest,version=2),dict(manifest,files={'other/file':'x'}),dict(manifest,files={'runtime/python.exe':'x'}),
                    dict(manifest,files={'runtime/missing.exe':'a'*64}),dict(manifest,components=[{'license':'unknown'}]),
                    dict(manifest,components=[dict(manifest['components'][0],notice='missing')]),
                    dict(manifest,components=[dict(manifest['components'][0],origin='file:local')]),
                    dict(manifest,components=[dict(manifest['components'][0],version='')]),
                    dict(manifest,components=[dict(manifest['components'][0],files=[])]),
                    dict(manifest,components=[dict(manifest['components'][0],files=['runtime/LICENSE.txt','missing'])]),
                    dict(manifest,components=[manifest['components'][0]])):
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError):d.locked_files(tmp_path)
    path.write_text(json.dumps(manifest));(tmp_path/'runtime/python.exe').write_text('modified')
    with pytest.raises(ValueError,match='modified'):d.locked_files(tmp_path)


def test_skill_locks_and_naming_privacy_are_enforced(tmp_path,monkeypatch):
    manifest,locked=repository(tmp_path,monkeypatch)
    assert d.check(tmp_path)==manifest
    path=tmp_path/'.agents/skills.lock.json'
    path.write_text(json.dumps([dict(locked[0],commit='main')]))
    with pytest.raises(ValueError,match='provenance'):d.skill_files(tmp_path)
    path.write_text(json.dumps(locked));(tmp_path/'.agents/skills/example/SKILL.md').write_text('modified')
    with pytest.raises(ValueError,match='modified'):d.skill_files(tmp_path)
    (tmp_path/'.agents/skills/example/SKILL.md').write_text('MIT upstream')
    path.write_text(json.dumps([dict(locked[0],license='Apache-2.0')]))
    with pytest.raises(ValueError,match='notice'):d.skill_files(tmp_path)
    (tmp_path/'.agents/skills/example/NOTICE.md').write_text('Apache notice')
    apache=dict(locked[0],license='Apache-2.0',files=dict(locked[0]['files'],**{'NOTICE.md':d.digest(tmp_path/'.agents/skills/example/NOTICE.md')}))
    path.write_text(json.dumps([apache]));assert d.skill_files(tmp_path)
    path.write_text(json.dumps(locked));(tmp_path/'.agents/skills/example/NOTICE.md').unlink()
    (tmp_path/'unknown.dll').write_text('unknown')
    with pytest.raises(ValueError,match='binary'):d.check(tmp_path)
    (tmp_path/'unknown.dll').unlink()
    (tmp_path/'Bad.py').write_text('clean')
    with pytest.raises(ValueError,match='casing'):d.check(tmp_path)
    (tmp_path/'Bad.py').unlink()
    (tmp_path/'sensitive.py').write_text('ghp_'+'A'*35)
    with pytest.raises(ValueError,match='Privacy'):d.check(tmp_path)


def test_generated_packages_share_source_preserve_private_data_and_limit_payload(tmp_path,monkeypatch):
    repository(tmp_path,monkeypatch)
    private=tmp_path/'setups/keyboard/.local/settings.json';private.parent.mkdir(parents=True);private.write_text('private')
    hidden=tmp_path/'app/accidentally-ignored.py';hidden.write_text('must not ship')
    d.packages(tmp_path);d.check(tmp_path)
    assert private.read_text()=='private'
    for mode in d.MODES:
        assert (tmp_path/'setups'/mode/'app/model.py').read_bytes()==(tmp_path/'app/model.py').read_bytes()
        assert f'--mode {mode}' in (tmp_path/'setups'/mode/'configure.cmd').read_text()
        assert not (tmp_path/'setups'/mode/'app/accidentally-ignored.py').exists()
    assert 'dependencies/ViGEmClient.dll' not in d.payload(tmp_path,'keyboard')
    assert d.payload(tmp_path)['README.md']==b'original'
    copy=tmp_path/'setups/xbox/app/model.py';copy.write_text('stale')
    with pytest.raises(ValueError,match='stale'):d.check(tmp_path)
    copy.unlink()
    with pytest.raises(ValueError,match='stale'):d.check(tmp_path)
    d.packages(tmp_path);assert copy.read_bytes()==b'original'


def test_release_runs_every_gate_and_builds_deterministic_allowlisted_archives(tmp_path,monkeypatch):
    repository(tmp_path,monkeypatch);calls=[]
    def runner(args,**kw):calls.append(args)
    built=d.release(tmp_path,runner)
    assert len(calls)==3 and len(built)==4
    before=[d.digest(path) for path in built]
    assert before==[d.digest(path) for path in d.release(tmp_path,runner)]
    with zipfile.ZipFile(built[1]) as archive:
        names=archive.namelist()
        assert 'runtime/python.exe' in names and not any('.local' in n or '.agents' in n for n in names)
        hashes=json.loads(archive.read('release-files.json'))
        assert all(hashlib.sha256(archive.read(name)).hexdigest()==checksum for name,checksum in hashes.items())
    assert built[0].with_suffix('.sha256').read_text().startswith(before[0])
    def failed(*a,**kw):raise subprocess.CalledProcessError(1,a)
    with pytest.raises(subprocess.CalledProcessError):d.release(tmp_path,failed)


def test_cli_success_failure_and_main_entry(tmp_path,monkeypatch,capsys):
    repository(tmp_path,monkeypatch)
    assert d.main(['check','--root',str(tmp_path)])==0
    (tmp_path/'runtime/python.exe').write_text('modified')
    assert d.main(['check','--root',str(tmp_path)])==1
    assert 'gate failed' in capsys.readouterr().err
    (tmp_path/'runtime/python.exe').write_bytes(b'python')
    monkeypatch.setattr(p,'inventory',d.inventory)
    monkeypatch.delitem(sys.modules,'tools.distribution')
    monkeypatch.setattr(sys,'argv',['distribution','check','--root',str(tmp_path)])
    with pytest.raises(SystemExit) as result:runpy.run_module('tools.distribution',run_name='__main__')
    assert result.value.code==0
