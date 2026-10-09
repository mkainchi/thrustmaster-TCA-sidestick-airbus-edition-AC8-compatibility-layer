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

const gameControls={xbox:['A','B','X','Y','LB','RB','LT','RT','L3','R3','START','BACK','UP','DOWN','LEFT','RIGHT'].map(value=>({value,label:value+' (Default unverified)'}))};
const profiles=JSON.parse(readFileSync('tests/fixtures/profiles.json','utf8'));
const handles=[];
afterEach(()=>{for(const handle of handles)handle?.close();handles.length=0;vi.restoreAllMocks();});
async function mount(mode=null, suggestion='00000409', active=false) {
  document.documentElement.innerHTML=readFileSync('app/web/index.html','utf8');
  const state={saved:{preferred_mode:mode,target_path:'',profiles:structuredClone(profiles)},defaults:structuredClone(profiles),
    layouts:[{id:'00000409',label:'QWERTY'}],suggested:suggestion,active,game_controls:gameControls};
  const result={state,dependencies:[],input:{available:false,message:'Disconnected.'},failure:null,saves:[],inputReads:0};
  const fetcher=async(url,options)=>{
    const route=url.split('/').pop();
    if(result.failure===route)throw Error('server unavailable');
    if(route==='key-action'){await result.hintWait;return {ok:true,json:async()=>result.hint||{text:'Default not verified; set this action manually in game.'}};}
    if(route==='input'){result.inputReads++;await result.inputWait;}
    if(route==='save'){result.saves.push(JSON.parse(options.body));await result.saveWait;return{ok:result.saveError===undefined,json:async()=>({message:result.saveError||'Saved locally.',field:result.errorField})};}
    return{ok:true,json:async()=>route==='state'?state:route==='dependencies'?result.dependencies:result.input};
  };
  vi.spyOn(window,'confirm').mockReturnValue(true);
  vi.spyOn(window,'setInterval').mockReturnValue(0);
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
  setXbox(t,'A+RB');
  t.$('axes-roll').value='1';t.$('axes-roll').onchange();
  t.$('invert-roll').checked=true;t.$('invert-roll').onchange();
  for(const field of ['deadzone','throttle_deadzone','yaw_threshold','camera_strength','high_g_button','poll_hz']) {
    t.$(field).value=field==='poll_hz'?'100':field==='high_g_button'?'4':'0.2';t.$(field).oninput();
  }
  t.saveError='Invalid mapping';await t.$('save').onclick();
  expect(t.$('message').textContent).toContain('Invalid mapping');expect(xboxValue(t)).toBe('A+RB');
  delete t.saveError;await t.$('save').onclick();
  expect(t.saves.at(-1).profile.buttons.q1).toBe('A+RB');
  expect(t.saves.at(-1).profile.axes.roll).toBe(1);expect(t.saves.at(-1).profile.invert.roll).toBe(true);
  expect(t.$('message').textContent).toBe('Saved locally.');
  const clean=new Event('beforeunload',{cancelable:true});window.dispatchEvent(clean);expect(clean.defaultPrevented).toBe(false);
  t.$('target-path').value='private installation';t.$('target-path').oninput();
  const dirty=new Event('beforeunload',{cancelable:true});window.dispatchEvent(dirty);expect(dirty.defaultPrevented).toBe(true);
  window.confirm.mockReturnValue(false);await t.mode('keyboard');expect(t.$('mode').value).toBe('xbox');
  t.$('reset').onclick();expect(xboxValue(t)).toBe('A+RB');
  window.confirm.mockReturnValue(true);t.$('reset').onclick();expect(xboxValue(t)).toBe('A');
  await t.mode('');expect(t.$('workspace').hidden).toBe(true);await t.handle.poll();
});

async function press(t, stick=[], quadrant=[]) {
  t.input={available:true,state:{stick:{axes:[0,0,0,0,0,0],buttons:stick,hat:[0,0]},quadrant:{axes:[0,0,0,0,0,0],buttons:quadrant,hat:[0,0]}}};
  await t.handle.poll();
}

it('selects new hardware presses and the matching diagram without discarding edits or moving focus',async()=>{
  const t=await mount('xbox');
  t.$('mode').focus();
  setXbox(t,'RB');
  t.$('mode').focus();
  await press(t,[3],[7]); // Initial held switches are a baseline.
  expect(t.$('control').value).toBe('buttons:s1');
  await press(t);await press(t,[],[2]);
  expect(t.$('control').value).toBe('buttons:q2');
  expect(t.$('show-quadrant').getAttribute('aria-pressed')).toBe('true');
  expect(t.$('stick-photo').hidden).toBe(true);
  expect(document.querySelector('[data-control="q2"]').getAttribute('aria-pressed')).toBe('true');
  expect(t.$('control-status').textContent).toContain('Quadrant 2');
  expect(document.activeElement).not.toBe(t.$('binding'));
  expect(t.$('message').textContent).toContain('Unsaved');
  await press(t,[],[2,9,16]);
  expect(t.$('control').value).toBe('buttons:q9');
  await press(t,[1,4,17],[3,16]);
  expect(t.$('control').value).toBe('buttons:q3');
  await press(t,[17],[]);expect(t.$('control').value).toBe('buttons:q3');
  await press(t,[17,11],[]);expect(t.$('control').value).toBe('buttons:s11');
  await press(t,[11],[]);expect(t.$('control').value).toBe('buttons:s11');
  t.$('control').value='buttons:s1';t.$('control').onchange();
  expect(xboxValue(t)).toBe('RB');
  expect(t.$('control-status').textContent).toBe('');
  t.$('control').value='keys:roll_left';await t.mode('keyboard');
  t.$('control').value='keys:roll_left';t.$('control').onchange();
  await press(t);await press(t,[4],[]);expect(t.$('control').value).toBe('buttons:s4');
});

it('consumes presses while editing or capturing and resumes only on a new press',async()=>{
  const t=await mount('keyboard');await press(t);
  t.$('binding').focus();t.$('binding').value='Space';t.$('binding').oninput();
  await press(t,[],[2]);expect(t.$('control').value).toBe('buttons:s1');
  expect(t.$('binding').value).toBe('Space');expect(document.activeElement).toBe(t.$('binding'));
  t.$('binding').blur();await press(t,[],[2]);expect(t.$('control').value).toBe('buttons:s1');
  t.$('capture').onclick();await press(t,[3],[]);
  expect(t.$('control').value).toBe('buttons:s1');expect(t.$('capture').textContent).toBe('Press key…');
  t.$('binding').blur();await press(t);await press(t,[3],[]);
  expect(t.$('control').value).toBe('buttons:s3');
  t.$('layout').focus();await press(t,[],[1]);expect(t.$('control').value).toBe('buttons:s3');
  t.$('layout').blur();await press(t);await press(t,[],[1]);expect(t.$('control').value).toBe('buttons:q1');
  t.input={available:false,message:'Disconnected.'};await t.handle.poll();
  await press(t,[4]);expect(t.$('control').value).toBe('buttons:q1');
  await press(t);await press(t,[4]);expect(t.$('control').value).toBe('buttons:s4');
  await t.mode('xbox');await press(t,[5]);expect(t.$('control').value).toBe('buttons:s1');
  await press(t);await press(t,[5]);expect(t.$('control').value).toBe('buttons:s5');
});

it('serializes input requests, ignores stale mode responses and tracks presses during save',async()=>{
  const t=await mount('xbox');await press(t);
  let release;t.inputWait=new Promise(resolve=>{release=resolve;});
  t.input.state.quadrant.buttons=[2];const pending=t.handle.poll();
  const duplicate=t.handle.poll();
  await t.mode('keyboard');release();await Promise.all([pending,duplicate]);
  expect(t.inputReads).toBe(2);
  expect(t.$('control').value).toBe('buttons:s1');
  t.inputWait=null;await press(t);t.$('use-layout').click();
  let saved;t.saveWait=new Promise(resolve=>{saved=resolve;});
  const saving=t.$('save').onclick();await press(t,[],[3]);
  expect(t.$('control').value).toBe('buttons:s1');saved();await saving;
  await press(t,[],[3]);expect(t.$('control').value).toBe('buttons:s1');
  await press(t);await press(t,[],[3]);expect(t.$('control').value).toBe('buttons:q3');
  t.inputWait=new Promise(resolve=>{release=resolve;});const closing=t.handle.poll();
  t.handle.close();release();await closing;
  expect(t.$('control').value).toBe('buttons:q3');
});

it('ignores failed input requests from an earlier mode or a closed editor',async()=>{
  const t=await mount('xbox');let reject;
  t.inputWait=new Promise((resolve,fail)=>{reject=fail;});const old=t.handle.poll();
  await t.mode('keyboard');reject(Error('old mode'));await old;
  expect(t.$('input-status').textContent).not.toContain('unavailable');
  t.inputWait=new Promise((resolve,fail)=>{reject=fail;});const closing=t.handle.poll();
  t.handle.close();reject(Error('closed'));await closing;
  expect(t.$('input-status').textContent).not.toContain('unavailable');
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
  expect(document.activeElement).toBe(t.$('xbox-output-0'));
  setXbox(t,'RB');
  expect(row.textContent).toContain('RB');
  expect(t.$('message').textContent).toContain('Unsaved');
  t.$('revert').click();
  expect(xboxValue(t)).toBe('A');
  expect(document.querySelector('[data-mapping="buttons:s11"]').textContent).toContain('UP');
  expect(t.$('revert').disabled).toBe(true);
  t.$('control').value='buttons:s5';t.$('control').onchange();
  expect(t.$('special-binding').textContent).toContain('High-G override');
  setXbox(t,'B');
  expect(document.querySelector('[data-mapping="buttons:s5"] .mapping-output').textContent).toBe('B + High-G override');
  expect(t.$('special-binding').textContent).toContain('binding also remains active');
  setXbox(t,'');
  t.$('high_g_button').value='0';t.$('high_g_button').oninput();
  expect(t.$('special-binding').textContent).toBe('');
  expect(document.querySelector('[data-mapping="buttons:s5"]').textContent).toContain('Unassigned');
});

it('rejects an invalid binding beside the editor before sending a save',async()=>{
  const t=await mount('xbox');
  t.state.saved.profiles.xbox.buttons.s1='NOT_A_BUTTON';await t.mode('xbox');
  await t.$('save').onclick();
  expect(t.saves).toHaveLength(0);
  expect(t.$('xbox-output-0').getAttribute('aria-invalid')).toBe('true');
  expect(t.$('binding-error').textContent).toContain('Xbox');
  expect(document.activeElement).toBe(t.$('xbox-output-0'));
  setXbox(t,'A');
  expect(t.$('xbox-output-0').hasAttribute('aria-invalid')).toBe(false);
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
  setXbox(t,'RB');
  window.confirm.mockReturnValue(false);t.$('revert').click();expect(xboxValue(t)).toBe('RB');
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

function xboxValue(t) { return [...t.$('xbox-rows').querySelectorAll('select')].map(input=>input.value).filter(Boolean).join('+'); }
function setXbox(t, value) {
  while(t.$('xbox-rows').children.length>1) t.$('xbox-rows').lastElementChild.querySelector('button').click();
  const values=value.split('+');
  values.forEach((part,index)=>{
    if(index)t.$('add-output').click();
    const select=t.$('xbox-output-'+index);select.value=part;select.onchange();
  });
}

it('edits Xbox combinations with distinct dropdowns and preserves pending rows',async()=>{
  const t=await mount('target-xbox');
  expect(t.$('keyboard-binding').hidden).toBe(true);
  expect(t.$('xbox-output-0').options.length).toBe(17);
  expect(t.$('xbox-output-0').selectedOptions[0].textContent).toContain('Default unverified');
  t.$('control').value='buttons:s6';t.$('control').onchange();
  expect(xboxValue(t)).toBe('L3+R3');
  t.$('add-output').click();
  expect(t.$('add-output').disabled).toBe(true);
  await t.$('save').onclick();expect(t.saves.at(-1).profile.buttons.s6).toBe('L3+R3');
  const third=t.$('xbox-output-2');
  expect([...third.options].find(option=>option.value==='L3').disabled).toBe(true);
  third.value='L3';third.onchange();expect(third.value).toBe('');
  third.value='LT';third.onchange();expect(xboxValue(t)).toBe('L3+R3+LT');
  t.$('xbox-rows').children[1].querySelector('button').click();
  expect(xboxValue(t)).toBe('L3+LT');
  setXbox(t,'');expect(t.$('add-output').disabled).toBe(true);
  await t.$('save').onclick();expect(t.saves.at(-1).profile.buttons.s6).toBe('');
  t.$('xbox-rows').querySelector('button').click();expect(t.$('xbox-output-0').value).toBe('');
  setXbox(t,gameControls.xbox.map(choice=>choice.value).join('+'));
  expect(t.$('add-output').disabled).toBe(true);
  t.$('mode').focus();await press(t);t.$('xbox-output-0').focus();await press(t,[3]);
  expect(t.$('control').value).toBe('buttons:s6');
  t.$('xbox-output-0').blur();await press(t,[3]);expect(t.$('control').value).toBe('buttons:s6');
  await press(t);await press(t,[3]);expect(t.$('control').value).toBe('buttons:s3');
  t.errorField='buttons:q2';t.saveError='Invalid output.';await t.$('save').onclick();
  expect(t.$('xbox-output-0').getAttribute('aria-invalid')).toBe('true');
  expect(document.activeElement).toBe(t.$('xbox-output-0'));
  await t.$('save').onclick();expect(t.$('binding-error').textContent).toBe('Invalid output.');
});

it('captures released modifiers and extended keys without overwriting completed chords',async()=>{
  const t=await mount('keyboard');t.$('use-layout').click();
  const down=options=>t.$('binding').onkeydown(new KeyboardEvent('keydown',options));
  const up=options=>t.$('binding').onkeyup(new KeyboardEvent('keyup',options));
  up({key:'Control',code:'ControlLeft'});
  t.$('capture').click();down({key:'Control',code:'ControlRight',ctrlKey:true});
  up({key:'Shift',code:'ShiftLeft'});expect(t.$('capture').textContent).toBe('Press key…');
  up({key:'Control',code:'ControlRight'});expect(t.$('binding').value).toBe('ControlRight');
  t.$('capture').click();down({key:'Control',code:'ControlLeft',ctrlKey:true});
  down({key:'a',code:'KeyA',ctrlKey:true});up({key:'Control',code:'ControlLeft'});
  expect(t.$('binding').value).toBe('ctrl+KeyA');
  for(const code of ['PrintScreen','F13','F24','Numpad1','Digit1']){
    t.$('capture').click();down({key:code,code});expect(t.$('binding').value).toBe(code);
  }
  t.$('capture').click();down({key:'MediaPlayPause',code:'MediaPlayPause'});
  expect(t.$('binding-error').textContent).toContain('Unsupported physical key');
  // A system modifier pressed before release remains unsupported.
  t.$('capture').click();down({key:'Control',code:'ControlLeft',ctrlKey:true});
  up({key:'Control',code:'ControlLeft',metaKey:true});
  expect(t.$('binding-error').textContent).toContain('system shortcuts');
  t.$('capture').click();down({key:'Alt',code:'AltLeft',altKey:true});t.$('binding').blur();
  up({key:'Alt',code:'AltLeft'});expect(t.$('binding').value).toBe('Digit1');
});

it('refreshes read-only action hints and discards stale or failed lookups without changing mappings',async()=>{
  const t=await mount('keyboard');
  expect(t.$('key-action').readOnly).toBe(true);
  t.hint={text:'Fixture default'};t.$('use-layout').click();
  await vi.waitFor(()=>expect(t.$('key-action').value).toBe('Fixture default'));
  let release;t.hintWait=new Promise(resolve=>release=resolve);
  t.$('control').value='buttons:s2';t.$('control').onchange();
  t.hintWait=undefined;t.hint={text:'New default'};
  t.$('control').value='buttons:s3';t.$('control').onchange();
  await vi.waitFor(()=>expect(t.$('key-action').value).toBe('New default'));
  release();await Promise.resolve();await Promise.resolve();
  expect(t.$('key-action').value).toBe('New default');
  t.failure='key-action';t.$('binding').value='F24';t.$('binding').oninput();
  expect(t.$('message').textContent).toBe('Unsaved changes.');
  await vi.waitFor(()=>expect(t.$('key-action').value).toContain('set its action manually'));
  await t.$('save').onclick();expect(t.saves.at(-1).profile.buttons.s3).toBe('F24');
  t.failure=null;let finish;t.hintWait=new Promise(resolve=>finish=resolve);
  t.$('control').onchange();await t.mode('xbox');finish();await Promise.resolve();await Promise.resolve();
  expect(t.$('keyboard-binding').hidden).toBe(true);
  await t.mode('keyboard');t.handle.close();finish();t.$('binding').oninput();
});
