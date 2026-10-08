from threading import Thread
import urllib.request
import urllib.error
import json
import pytest
from app.server import create_server
from app import server as s
from http.client import HTTPConnection
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


@contextmanager
def live(root,fixture):
    server=create_server(root,fixture);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    conn=HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:yield server,conn
    finally:conn.close();server.shutdown();server.server_close();thread.join()


def http(server,conn,method,route,body=None,headers=None):
    path='/'+server.token+'/'+route
    base={'Origin':f'http://127.0.0.1:{server.server_port}','Content-Type':'application/json'}
    base.update(headers or {})
    conn.request(method,path,body,base);response=conn.getresponse();return response.status,response.read(),response.headers


def test_loopback_token_origin_and_confirmed_layout_save(tmp_path):
    server = create_server(tmp_path, fixture={'layouts': [{'id': '00000409', 'label': 'QWERTY'}], 'suggested': '00000409', 'ready': True})
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    base = server.url
    try:
        state = json.load(urllib.request.urlopen(base + 'state'))
        assert state['saved']['preferred_mode'] is None
        assert state['defaults']['keyboard']['layout'] is None
        payload = {'mode': 'keyboard', 'profile': state['defaults']['keyboard'], 'target_path': ''}
        req = urllib.request.Request(base+'save', json.dumps(payload).encode(), {'Content-Type': 'application/json', 'Origin': 'https://example.invalid'})
        with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
        assert e.value.code == 403
        payload['profile']['layout'] = '00000409'
        req = urllib.request.Request(base+'save', json.dumps(payload).encode(), {'Content-Type': 'application/json', 'Origin': base.split('/'+server.token)[0]})
        assert json.load(urllib.request.urlopen(req))['message'] == 'Saved. Run emulate.cmd to start Keyboard · TARGET.'
        assert (tmp_path/'.local'/'config.json').exists()
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_assets_input_authentication_validation_and_session_guard(tmp_path,monkeypatch):
    fixture={'layouts':[{'id':'00000409','label':'QWERTY'}],'suggested':None,'ready':False}
    fixture_path=tmp_path/'fixture.json';fixture_path.write_text(json.dumps(fixture))
    with live(tmp_path,fixture_path) as (server,conn):
        server.handle_error(None,None)
        for name in ('','ui.js','logic.js','boot.js','style.css'):
            code,body,headers=http(server,conn,'GET',name);assert code==200 and body
            assert "script-src 'self'" in headers['Content-Security-Policy']
            assert headers['Referrer-Policy']=='no-referrer'
        assert http(server,conn,'GET','unknown')[0]==404
        assert http(server,conn,'GET','state?wrong')[0]==404
        assert http(server,conn,'GET','state',headers={'Host':'example.invalid'})[0]==404
        assert http(server,conn,'GET','input')[0]==200
        fixture['input']={'available':True,'state':{}};fixture_path.write_text(json.dumps(fixture))
        assert json.loads(http(server,conn,'GET','input')[1])['available']
        payload=json.dumps({'mode':'target-xbox','target_path':'fixture-target'})
        assert http(server,conn,'POST','dependencies',payload)[0]==200
        fixture['ready']=True;fixture_path.write_text(json.dumps(fixture))
        assert all(i['ready'] for i in json.loads(http(server,conn,'POST','dependencies',payload)[1]))
        assert http(server,conn,'POST','unknown','{}')[0]==403
        assert http(server,conn,'POST','save','{}',{'Content-Type':'text/plain'})[0]==415
        for payload in ('', 'invalid','[]','{}',json.dumps({'mode':'other','target_path':''}),json.dumps({'mode':'xbox','target_path':123})):
            assert http(server,conn,'POST','dependencies',payload)[0]==400
        assert http(server,conn,'POST','dependencies','x'*32001)[0]==400
        assert http(server,conn,'POST','dependencies','',{'Content-Length':'invalid'})[0]==400
        cfg=s.defaults('keyboard');cfg['layout']='0000040c'
        assert http(server,conn,'POST','save',json.dumps({'mode':'keyboard','profile':cfg,'target_path':''}))[0]==400
        local=tmp_path/'.local';local.mkdir();(local/'session.json').write_text('{}')
        assert http(server,conn,'POST','save',json.dumps({'mode':'xbox','profile':s.defaults('xbox'),'target_path':''}))[0]==409
        (local/'session.json').unlink()
        monkeypatch.setattr(s.Store,'save',lambda *a:(_ for _ in ()).throw(OSError('private path')))
        code,body,_=http(server,conn,'POST','save',json.dumps({'mode':'xbox','profile':s.defaults('xbox'),'target_path':''}))
        assert code==500 and b'private path' not in body
        monkeypatch.setattr(s,'WEB',tmp_path)
        assert http(server,conn,'GET','ui.js')[0]==503
        (local/'config.json').write_text('invalid')
        assert http(server,conn,'GET','state')[0]==503


def test_real_adapter_paths_use_layout_and_input_interfaces(tmp_path,monkeypatch):
    layout=SimpleNamespace(items=[{'id':'00000409','label':'QWERTY'}],suggested='00000409',resolve=lambda *a:(1004,[]))
    modes=[]
    input=SimpleNamespace(snapshot=lambda mode:modes.append(mode) or {'stick':{},'quadrant':{}})
    monkeypatch.setattr(s,'WindowsLayouts',lambda:layout);monkeypatch.setattr(s,'Joysticks',lambda:input)
    monkeypatch.setattr(s,'status',lambda *a:[{'ready':True}])
    selected=create_server(tmp_path,{'layouts':[],'suggested':None,'ready':True},'xbox')
    thread=Thread(target=selected.serve_forever,daemon=True);thread.start()
    try:assert json.load(urllib.request.urlopen(selected.url+'state'))['saved']['preferred_mode']=='xbox'
    finally:selected.shutdown();selected.server_close();thread.join()
    with live(tmp_path,None) as (server,conn):
        assert http(server,conn,'POST','dependencies',json.dumps({'mode':'xbox','target_path':''}))[0]==200
        assert http(server,conn,'GET','input')[0]==200 and modes==['xbox']
        cfg=s.defaults('keyboard');cfg['layout']='00000409'
        assert http(server,conn,'POST','save',json.dumps({'mode':'keyboard','profile':cfg,'target_path':''}))[0]==200
        cfg=s.defaults('target-xbox');s.Store(tmp_path).save('target-xbox',cfg,'')
        (tmp_path/'.local'/'session.json').write_text('{}')
        assert http(server,conn,'GET','input')[0]==200 and modes[-1]=='target-xbox'
        (tmp_path/'.local'/'session.json').unlink()
        assert http(server,conn,'GET','input')[0]==200 and modes[-1]=='xbox'
        input.snapshot=lambda mode:(_ for _ in ()).throw(RuntimeError('unavailable'))
        assert http(server,conn,'GET','input')[0]==503


def test_save_error_preserves_message_and_identifies_invalid_field(tmp_path):
    fixture={'layouts':[{'id':'00000409','label':'QWERTY'}],'suggested':None,'ready':True}
    with live(tmp_path,fixture) as (server,conn):
        cfg=s.defaults('xbox');cfg['buttons']['s3']='A+BAD'
        code,body,_=http(server,conn,'POST','save',json.dumps({'mode':'xbox','profile':cfg,'target_path':''}))
        error=json.loads(body)
        assert code==400 and error['field']=='buttons:s3'
        assert 'Xbox button names' in error['message']
        assert not (tmp_path/'.local'/'config.json').exists()
        cfg=s.defaults('keyboard');cfg['layout']='0000040c'
        code,body,_=http(server,conn,'POST','save',json.dumps({'mode':'keyboard','profile':cfg,'target_path':''}))
        assert code==400 and json.loads(body)['field']=='layout'


@pytest.mark.parametrize('section,key',[('keys','roll_left'),('buttons','s3')])
def test_keyboard_translation_error_identifies_binding_without_saving(tmp_path,monkeypatch,section,key):
    def resolve(binding,layout):
        if binding=='☃':
            raise ValueError('A character is unavailable in the selected layout. Capture its physical key instead.')
        return 1004,[]
    monkeypatch.setattr(s,'WindowsLayouts',lambda:SimpleNamespace(items=[{'id':'00000409','label':'QWERTY'}],suggested=None,resolve=resolve))
    monkeypatch.setattr(s,'Joysticks',lambda:SimpleNamespace())
    cfg=s.defaults('keyboard');cfg['layout']='00000409';cfg[section][key]='☃'
    with live(tmp_path,None) as (server,conn):
        code,body,_=http(server,conn,'POST','save',json.dumps({'mode':'keyboard','profile':cfg,'target_path':''}))
        error=json.loads(body)
        assert code==400 and error['field']==f'{section}:{key}'
        assert 'Capture its physical key' in error['message']
        assert not (tmp_path/'.local'/'config.json').exists()


@pytest.mark.parametrize('mode,label',[('xbox','Xbox · direct input'),('target-xbox','TARGET → Xbox')])
def test_save_success_names_the_visible_mode(tmp_path,mode,label):
    with live(tmp_path,{'layouts':[],'suggested':None,'ready':True}) as (server,conn):
        code,body,_=http(server,conn,'POST','save',json.dumps({'mode':mode,'profile':s.defaults(mode),'target_path':''}))
        assert code==200 and json.loads(body)['message']==f'Saved. Run emulate.cmd to start {label}.'


@pytest.mark.parametrize('name',['sidestick.png','quadrant.png','sidestick-grip.png','quadrant-grip.png'])
def test_device_photos_only_serve_allowlisted_private_images(tmp_path,name):
    images=tmp_path/'.local'/'device-images';images.mkdir(parents=True)
    (images/'private.png').write_bytes(b'private')
    with live(tmp_path,{'layouts':[],'suggested':None,'ready':True}) as (server,conn):
        code,body,_=http(server,conn,'GET','device/'+name)
        assert code==404 and json.loads(body)=={'message':'Not found.'}
        (images/name).write_bytes(b'fixture image')
        code,body,headers=http(server,conn,'GET','device/'+name)
        assert code==200 and body==b'fixture image'
        assert headers['Content-Type']=='image/png'
        for route in ('device/private.png','device/../config.json','device/%2e%2e/config.json','device/sidestick.webp'):
            code,body,_=http(server,conn,'GET',route)
            assert code==404 and json.loads(body)=={'message':'Not found.'}
