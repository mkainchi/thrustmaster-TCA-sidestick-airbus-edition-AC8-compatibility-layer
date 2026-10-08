import {readFileSync} from 'node:fs';
import {it, expect, vi, afterEach} from 'vitest';
import {start} from '../app/web/ui.js';

it('opens without choosing a mode or keyboard layout for the gamer', async()=>{
  document.documentElement.innerHTML=readFileSync('app/web/index.html','utf8');
  const base = {version:1,layout:null,buttons:{s1:'A'},keys:{roll_left:'ArrowLeft'},axes:{roll:0},invert:{pitch:true},deadzone:.04};
  const state={saved:{preferred_mode:null,target_path:'',profiles:{keyboard:base,xbox:base,'target-xbox':base}},
    defaults:{keyboard:base,xbox:base,'target-xbox':base},layouts:[{id:'00000409',label:'QWERTY'}],suggested:'00000409',active:false};
  const fetcher=vi.fn(async()=>({ok:true,json:async()=>state}));
  const handle=await start(document,window,fetcher);
  expect(document.getElementById('mode').value).toBe('');
  expect(document.getElementById('workspace').hidden).toBe(true);
  handle.close();
});

const profiles=JSON.parse(readFileSync('tests/fixtures/profiles.json','utf8'));
const handles=[];
afterEach(()=>{for(const handle of handles)handle?.close();handles.length=0;vi.restoreAllMocks();});
async function mount(mode=null, suggestion='00000409', active=false) {
  document.documentElement.innerHTML=readFileSync('app/web/index.html','utf8');
  const state={saved:{preferred_mode:mode,target_path:'',profiles:structuredClone(profiles)},defaults:structuredClone(profiles),
    layouts:[{id:'00000409',label:'QWERTY'}],suggested:suggestion,active};
  const result={state,dependencies:[],input:{available:false,message:'Disconnected.'},failure:null,saves:[]};
  const fetcher=async(url,options)=>{
    const route=url.split('/').pop();
    if(result.failure===route)throw Error('server unavailable');
    if(route==='save'){result.saves.push(JSON.parse(options.body));return{ok:result.saveError===undefined,json:async()=>({message:result.saveError||'Saved locally.',field:result.errorField})};}
    return{ok:true,json:async()=>route==='state'?state:route==='dependencies'?result.dependencies:result.input};
  };
  vi.spyOn(window,'confirm').mockReturnValue(true);
  result.handle=await start(document,window,fetcher);handles.push(result.handle);
  result.$=id=>document.getElementById(id);
  result.mode=async next=>{result.$('mode').value=next;await result.$('mode').onchange();};
  return result;
}

it('maps the selected physical control, calibrates input and retains a failed save',async()=>{
  const t=await mount('xbox');
  t.dependencies=[{id:'runtime',label:'Runtime',ready:false,url:'',remedy:'Restore files.'},
    {id:'vigem',label:'Driver',ready:false,url:'https://example.invalid',remedy:'Install driver.'}];
  await t.$('recheck').onclick();
  expect(t.$('dependencies').textContent).toContain('Restore files.');
  expect(t.$('dependencies').querySelector('a').rel).toContain('noreferrer');
  const marker=document.querySelector('[data-control="s11"]');
  marker.onclick();expect(t.$('control').value).toBe('buttons:s11');
  marker.onkeydown(new KeyboardEvent('keydown',{key:'Escape'}));
  marker.onkeydown(new KeyboardEvent('keydown',{key:' '}));
  t.$('control').value='buttons:q1';t.$('control').onchange();
  t.$('binding').value='A+RB';t.$('binding').oninput();
  t.$('axes-roll').value='1';t.$('axes-roll').onchange();
  t.$('invert-roll').checked=true;t.$('invert-roll').onchange();
  for(const field of ['deadzone','throttle_deadzone','yaw_threshold','camera_strength','high_g_button','poll_hz']) {
    t.$(field).value=field==='poll_hz'?'100':field==='high_g_button'?'4':'0.2';t.$(field).oninput();
  }
  t.saveError='Invalid mapping';await t.$('save').onclick();
  expect(t.$('message').textContent).toContain('Invalid mapping');expect(t.$('binding').value).toBe('A+RB');
  delete t.saveError;await t.$('save').onclick();
  expect(t.saves.at(-1).profile.buttons.q1).toBe('A+RB');
  expect(t.saves.at(-1).profile.axes.roll).toBe(1);expect(t.saves.at(-1).profile.invert.roll).toBe(true);
  expect(t.$('message').textContent).toBe('Saved locally.');
  const clean=new Event('beforeunload',{cancelable:true});window.dispatchEvent(clean);expect(clean.defaultPrevented).toBe(false);
  t.$('target-path').value='private installation';t.$('target-path').oninput();
  const dirty=new Event('beforeunload',{cancelable:true});window.dispatchEvent(dirty);expect(dirty.defaultPrevented).toBe(true);
  window.confirm.mockReturnValue(false);await t.mode('keyboard');expect(t.$('mode').value).toBe('xbox');
  t.$('reset').onclick();expect(t.$('binding').value).toBe('A+RB');
  window.confirm.mockReturnValue(true);t.$('reset').onclick();expect(t.$('binding').value).toBe('A');
  await t.mode('');expect(t.$('workspace').hidden).toBe(true);await t.handle.poll();
});

it('requires a layout, captures a chord and handles unsupported key events',async()=>{
  const t=await mount();await t.mode('keyboard');
  expect(t.$('save').disabled).toBe(true);
  t.$('use-layout').onclick();expect(t.$('layout').value).toBe('00000409');
  expect(t.$('save').disabled).toBe(false);
  t.$('binding').onkeydown(new KeyboardEvent('keydown',{key:'a',code:'KeyA'}));
  t.$('capture').onclick();t.$('binding').onkeydown(new KeyboardEvent('keydown',{key:'Shift',code:'ShiftLeft',shiftKey:true}));
  expect(t.$('capture').textContent).toBe('Press key…');
  t.$('binding').onkeydown(new KeyboardEvent('keydown',{key:'A',code:'KeyA',shiftKey:true}));
  expect(t.$('binding').value).toBe('shift+KeyA');
  await t.$('save').onclick();
  expect(t.saves[0].profile.buttons.s1).toEqual({code:'KeyA',modifiers:['shift']});
  await t.mode('xbox');await t.mode('keyboard');expect(t.$('binding').value).toBe('shift+KeyA');
  t.$('control').value='keys:roll_left';t.$('control').onchange();expect(t.$('binding').value).toBe('ArrowLeft');
  t.$('capture').onclick();t.$('binding').onkeydown(new KeyboardEvent('keydown',{key:'Dead',code:'KeyA'}));
  expect(t.$('message').textContent).toContain('standard game key');
  t.$('binding').onblur();expect(t.$('capture').textContent).toBe('Capture key');
  t.$('capture').onclick();t.$('binding').value='Space';t.$('binding').oninput();expect(t.$('capture').textContent).toBe('Capture key');
});

it('shows dependency failures, missing suggestions, live controls and loss of input',async()=>{
  const t=await mount('keyboard',null,true);expect(t.$('save').disabled).toBe(true);
  t.$('use-layout').onclick();expect(t.$('message').textContent).toContain('Windows layout unavailable');
  t.dependencies=[{id:'target',label:'TARGET',ready:true,path:'fixture-target',url:'',remedy:''}];
  await t.$('recheck').onclick();expect(t.$('target-path').value).toBe('fixture-target');
  expect(t.$('dependency-message').textContent).toContain('Ready');
  t.failure='dependencies';await t.$('recheck').onclick();expect(t.$('dependency-message').textContent).toContain('failed');
  await t.handle.poll();expect(t.$('input-status').textContent).toBe('Disconnected.');
  t.input={available:true,state:{stick:{axes:[0,.5],buttons:[1],hat:[0,0]},quadrant:{axes:[1],buttons:[2],hat:[0,0]}}};
  await t.handle.poll();expect(document.querySelector('[data-control="s1"]').classList.contains('live')).toBe(true);
  expect(document.querySelector('[data-control="q2"]').classList.contains('live')).toBe(true);
  expect(t.$('axis-preview').textContent).toContain('0.50');
  t.failure='input';await t.handle.poll();expect(t.$('input-status').textContent).toContain('unavailable');
  expect(document.querySelector('.control.live')).toBeNull();expect(t.$('axis-preview').textContent).toBe('');
  t.failure=null;t.input={available:false,message:'Disconnected.'};await t.handle.poll();
  expect(document.querySelector('.control.live')).toBeNull();
});

it('reports an unavailable server without starting a poller',async()=>{
  document.documentElement.innerHTML=readFileSync('app/web/index.html','utf8');
  expect(await start(document,window,async()=>{throw Error('offline');})).toBeNull();
  expect(document.getElementById('load-error').textContent).toContain('Reopen configure.cmd');
});

it('reviews assignments and updates the overview while keeping calibration optional',async()=>{
  const t=await mount('xbox');
  expect(t.$('calibration').open).toBe(false);
  const row=document.querySelector('[data-mapping="buttons:s11"]');
  expect(row.textContent).toContain('UP');
  expect(row.querySelector('button').textContent).toBe('Edit Sidestick 11');
  row.querySelector('button').click();
  expect(t.$('control').value).toBe('buttons:s11');
  expect(document.activeElement).toBe(t.$('binding'));
  t.$('binding').value='RB';t.$('binding').oninput();
  expect(row.textContent).toContain('RB');
  expect(t.$('message').textContent).toContain('Unsaved');
  t.$('revert').click();
  expect(t.$('binding').value).toBe('A');
  expect(document.querySelector('[data-mapping="buttons:s11"]').textContent).toContain('UP');
  expect(t.$('revert').disabled).toBe(true);
  t.$('control').value='buttons:s5';t.$('control').onchange();
  expect(t.$('special-binding').textContent).toContain('High-G override');
  t.$('binding').value='B';t.$('binding').oninput();
  expect(document.querySelector('[data-mapping="buttons:s5"] .mapping-output').textContent).toBe('B + High-G override');
  expect(t.$('special-binding').textContent).toContain('binding also remains active');
  t.$('binding').value='';t.$('binding').oninput();
  t.$('high_g_button').value='0';t.$('high_g_button').oninput();
  expect(t.$('special-binding').textContent).toBe('');
  expect(document.querySelector('[data-mapping="buttons:s5"]').textContent).toContain('Unassigned');
});

it('rejects an invalid binding beside the editor before sending a save',async()=>{
  const t=await mount('xbox');
  t.$('binding').value='NOT_A_BUTTON';t.$('binding').oninput();
  await t.$('save').onclick();
  expect(t.saves).toHaveLength(0);
  expect(t.$('binding').getAttribute('aria-invalid')).toBe('true');
  expect(t.$('binding-error').textContent).toContain('Xbox');
  expect(document.activeElement).toBe(t.$('binding'));
  t.$('binding').value='A';t.$('binding').oninput();
  expect(t.$('binding').hasAttribute('aria-invalid')).toBe(false);
  expect(t.$('binding-error').textContent).toBe('');
});

it('reveals and focuses the exact field reported by save validation',async()=>{
  const t=await mount('keyboard');t.$('use-layout').click();
  t.saveError='Choose a supported key.';t.errorField='keys:roll_left';
  await t.$('save').onclick();
  expect(t.$('control').value).toBe('keys:roll_left');
  expect(t.$('binding').getAttribute('aria-invalid')).toBe('true');
  expect(t.$('binding-error').textContent).toContain('supported key');
  expect(document.activeElement).toBe(t.$('binding'));
  t.errorField='poll_hz';t.saveError='Input frequency must be between 10 and 500 Hz.';
  await t.$('save').onclick();
  expect(t.$('calibration').open).toBe(true);
  expect(t.$('poll_hz-error').textContent).toContain('10 and 500');
  expect(document.activeElement).toBe(t.$('poll_hz'));
});

it('keeps device selection and handedness usable when a diagram is unavailable',async()=>{
  const t=await mount('xbox');
  t.$('show-quadrant').click();expect(t.$('control').value).toBe('buttons:q1');
  expect(t.$('stick-photo').hidden).toBe(true);
  t.$('show-stick').click();expect(t.$('control').value).toBe('buttons:s1');
  t.$('handedness').value='left';t.$('handedness').onchange();
  expect(document.querySelector('.sidestick-photo').dataset.hand).toBe('left');
  for(const image of document.querySelectorAll('.photo-frame img')) {
    image.onerror();expect(image.parentElement.hidden).toBe(true);
    expect(image.parentElement.nextElementSibling.hidden).toBe(false);
    image.onload();expect(image.parentElement.hidden).toBe(false);
    expect(image.parentElement.nextElementSibling.hidden).toBe(true);
  }
  t.$('binding').value='RB';t.$('binding').oninput();
  window.confirm.mockReturnValue(false);t.$('revert').click();expect(t.$('binding').value).toBe('RB');
});

it('opens calibration for invalid numeric input without sending or discarding edits',async()=>{
  const t=await mount('xbox');
  t.$('poll_hz').value='501';t.$('poll_hz').oninput();
  await t.$('save').onclick();expect(t.saves).toHaveLength(0);
  expect(t.$('calibration').open).toBe(true);
  expect(document.activeElement).toBe(t.$('poll_hz'));
  expect(t.$('poll_hz-error').textContent).toContain('10 to 500');
  expect(t.$('poll_hz').value).toBe('501');
  t.$('poll_hz').value='125';t.$('poll_hz').oninput();
  t.errorField='axes:roll';t.saveError='Choose an input axis.';
  await t.$('save').onclick();expect(document.activeElement).toBe(t.$('axes-roll'));
  t.errorField='unknown';await t.$('save').onclick();expect(t.$('message').textContent).toContain('input axis');
});

it('executes the browser boot module',async()=>{
  const t=await mount();
  const fetcher=async()=>({ok:true,json:async()=>t.state});
  vi.stubGlobal('fetch',fetcher);vi.spyOn(window,'setInterval').mockReturnValue(0);
  await import('../app/web/boot.js');vi.unstubAllGlobals();
});
