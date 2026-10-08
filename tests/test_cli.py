from app.cli import main
from app import cli
from types import SimpleNamespace
import pytest
import runpy
import sys


def test_configuration_browser_server_and_cleanup(tmp_path,monkeypatch,capsys):
    calls=[]
    server=SimpleNamespace(url='http://127.0.0.1:1/private/',serve_forever=lambda:calls.append('serve'),server_close=lambda:calls.append('close'))
    monkeypatch.setattr(cli,'create_server',lambda *a:server)
    monkeypatch.setattr(cli.webbrowser,'open',lambda url:calls.append(url))
    assert main(['configure','--root',str(tmp_path)])==0
    assert calls==[server.url,'serve','close']
    assert main(['configure','--root',str(tmp_path),'--no-browser'])==0
    assert server.url in capsys.readouterr().out
    def interrupt():raise KeyboardInterrupt()
    server.serve_forever=interrupt
    assert main(['configure','--root',str(tmp_path)])==0
    assert calls[-1]=='close'


def test_emulation_errors_seconds_validation_and_entrypoint(tmp_path,monkeypatch,capsys):
    calls=[];monkeypatch.setattr(cli,'run',lambda root,seconds,expected_mode:calls.append(seconds))
    assert main(['emulate','--root',str(tmp_path),'--seconds','2'])==0
    assert calls==[2]
    assert main(['emulate','--test-fixture','fake'])==1
    monkeypatch.setattr(cli,'request_stop',lambda root:True)
    assert main(['emulate','--stop'])==0
    assert 'Stop requested' in capsys.readouterr().out
    def unavailable(*a,**kw):raise OSError('private path')
    monkeypatch.setattr(cli,'run',unavailable)
    assert main(['emulate'])==1
    assert 'private path' not in capsys.readouterr().err
    with pytest.raises(SystemExit):main(['emulate','--seconds','0'])
    monkeypatch.setattr(sys,'argv',['app','emulate','--stop'])
    with pytest.raises(SystemExit) as result:runpy.run_module('app',run_name='__main__')
    assert result.value.code==0


def test_missing_preferred_mode_and_stop_without_session(tmp_path, capsys,monkeypatch):
    from contextlib import nullcontext
    from app.session import run
    monkeypatch.setattr(cli,'run',lambda root,seconds,expected_mode:run(root,seconds,guard=nullcontext,expected_mode=expected_mode))
    assert main(['emulate', '--root', str(tmp_path)]) == 1
    assert 'configure.cmd' in capsys.readouterr().err
    assert main(['emulate', '--stop', '--root', str(tmp_path)]) == 0
    assert 'No active session' in capsys.readouterr().out
