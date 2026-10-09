import {test as base, expect} from '@playwright/test';
import {mkdtemp, writeFile, readFile, rm, mkdir, rename} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';

const test = base.extend({editor: async({page}, use) => {
  const root = await mkdtemp(join(tmpdir(), 'tca-e2e-'));
  const fixture = join(root, 'fixture.json');
  const data = {layouts: [{id:'00000409',label:'QWERTY · English'}, {id:'0000040c',label:'AZERTY · French'}, {id:'00000407',label:'QWERTZ · German'}], suggested:'0000040c', ready:false};
  const swaps={'00000409':{},'0000040c':{A:'Q',Q:'A',W:'Z',Z:'W'},'00000407':{Y:'Z',Z:'Y'}};
  data.key_translations=Object.fromEntries(data.layouts.map(({id})=>[id,Object.fromEntries(
    [...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'].map(character=>[character,{
      code:/[0-9]/.test(character)?'Digit'+character:'Key'+(swaps[id][character.toUpperCase()]||character.toUpperCase()),
      modifiers:(/[A-Z]/.test(character)||(id==='0000040c'&&/[0-9]/.test(character)))?['shift']:[]
    }]))]));
  await writeFile(fixture, JSON.stringify(data));
  const python = process.env.TCA_TEST_PYTHON || '.local/dev-venv/Scripts/python.exe';
  const child = spawn(python, ['-B', '-m', 'app', 'configure', '--root', root, '--test-fixture', fixture, '--no-browser'], {cwd:process.cwd(), windowsHide:true});
  let output='', errors='';
  child.stderr.on('data', chunk=>{errors+=chunk;});
  const url = await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('Editor did not start: '+errors)),10000);
    child.stdout.on('data',chunk=>{output+=chunk; const match=output.match(/http:\/\/127\.0\.0\.1:\d+\/[^\s]+\//); if(match){clearTimeout(timer);resolve(match[0]);}});
    child.on('exit',()=>{clearTimeout(timer);reject(Error('Editor exited: '+errors));});
  });
  const external=[];
  page.on('request', request=>{if(!request.url().startsWith(url) && !request.url().startsWith('data:')) external.push(request.url());});
  try { await page.goto(url); await use({root,fixture,data,url,external}); }
  finally { child.kill(); await new Promise(resolve=>child.exitCode!==null ? resolve() : child.once('exit',resolve)); await rm(root,{recursive:true,force:true}); }
}});

test('first run does not assume a mode or the suggested French layout', async({page,editor})=>{
  await expect(page.getByLabel('Preferred mode')).toHaveValue('');
  await expect(page.locator('#workspace')).toBeHidden();
  await page.getByLabel('Preferred mode').selectOption('keyboard');
  await expect(page.getByLabel('Layout used in the game')).toHaveValue('');
  await expect(page.getByRole('button',{name:'Save configuration'})).toBeDisabled();
  await expect(page.locator('#layout-help')).toContainText('AZERTY');
  await expect(page.getByRole('button',{name:'Sidestick button 1',exact:true})).toBeVisible();
  expect(editor.external).toEqual([]);
});

test('all device diagrams render offline without private reference images',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await expect.poll(()=>page.locator('.photo-frame img').evaluateAll(images=>images.map(image=>[image.naturalWidth,image.naturalHeight]))).toEqual([[1920,1080],[152,125],[1920,1080],[145,115]]);
  await expect(page.getByRole('button',{name:'Sidestick button 3',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Quadrant',exact:true}).click();
  await page.getByRole('button',{name:'Quadrant button 2',exact:true}).click();
  await expect(page.locator('#control')).toHaveValue('buttons:q2');
  expect(editor.external).toEqual([]);
});

test('physical presses select the matching device while binding edits and held switches remain stable',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  const update=async(stick=[],quadrant=[],available=true)=>{
    editor.data.input={available,message:'Disconnected.',state:{stick:{axes:[0,0,0,0,0,0],buttons:stick,hat:[0,0]},quadrant:{axes:[0,0,0,0,0,0],buttons:quadrant,hat:[0,0]}}};
    await writeFile(editor.fixture+'.tmp',JSON.stringify(editor.data));await rename(editor.fixture+'.tmp',editor.fixture);
    // A transient fixture read failure also clears highlights. Wait for the
    // requested successful snapshot so it cannot stand in for a release.
    await expect.poll(()=>page.evaluate(()=>({
      status:document.querySelector('#input-status').textContent,
      buttons:[...new Set([...document.querySelectorAll('[data-control].live')].map(button=>button.dataset.control))].sort()
    }))).toEqual({status:available?'Live input · move a lever or press a button.':'Disconnected.',buttons:available?[...stick.map(button=>'s'+button),...quadrant.map(button=>'q'+button)].sort():[]});
  };
  await update();await expect(page.locator('#input-status')).toContainText('Live input');
  await page.locator('#mode').focus();await update([],[1]);
  await expect(page.locator('#control')).toHaveValue('buttons:q1');
  await expect(page.locator('#mode')).toBeFocused();
  await update();await expect(page.locator('[data-control="q1"]')).not.toHaveClass(/live/);
  await page.getByRole('button',{name:'Sidestick',exact:true}).click();
  await setXbox(page,'RB');await page.getByRole('heading',{name:'Hardware mappings'}).click();
  await update([],[2]);await expect(page.locator('#control')).toHaveValue('buttons:q2');
  await expect(page.locator('#show-quadrant')).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('[data-control="q2"]')).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('#control-status')).toContainText('Quadrant 2');
  await expect(page.locator('#xbox-output-0')).not.toBeFocused();
  const images=join(process.cwd(),'.local/button-selection');await mkdir(images,{recursive:true});
  await page.screenshot({path:join(images,'desktop.png'),fullPage:true});
  await setXbox(page,'X');await update([11],[2]);
  await expect(page.locator('[data-control="s11"]')).toHaveClass(/live/);
  await expect(page.locator('#control')).toHaveValue('buttons:q2');
  await expect(page.locator('#xbox-output-0')).toHaveValue('X');await expect(page.locator('#xbox-output-0')).toBeFocused();
  await page.getByRole('heading',{name:'Hardware mappings'}).click();
  await expect(page.locator('#control')).toHaveValue('buttons:q2');
  await update();await expect(page.locator('[data-control="s11"]')).not.toHaveClass(/live/);
  await update([11]);await expect(page.locator('#control')).toHaveValue('buttons:s11');
  await update([],[],false);await expect(page.locator('#input-status')).toHaveText('Disconnected.');
  await update([3]);await expect(page.locator('[data-control="s3"]')).toHaveClass(/live/);
  await expect(page.locator('#control')).toHaveValue('buttons:s11');
  await update();await expect(page.locator('[data-control="s3"]')).not.toHaveClass(/live/);
  await update([3]);await expect(page.locator('#control')).toHaveValue('buttons:s3');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  const cfg=JSON.parse(await readFile(join(editor.root,'.local/config.json'),'utf8'));
  expect(cfg.profiles.xbox.buttons.s1).toBe('RB');expect(cfg.profiles.xbox.buttons.q2).toBe('X');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:join(images,'narrow.png'),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect(editor.external).toEqual([]);
});

for (const mode of ['keyboard','xbox','target-xbox']) {
  test(`${mode}: configure, resolve prerequisites, save and reopen`, async({page,editor})=>{
    await page.getByLabel('Preferred mode').selectOption(mode);
    if(mode!=='xbox') {
      await page.getByLabel('TARGET installation folder').fill('bad-folder');
      await page.getByRole('button',{name:'Recheck dependencies'}).click();
      await expect(page.locator('#dependencies')).toContainText('Thrustmaster TARGET · Needs attention');
      await page.getByLabel('TARGET installation folder').fill('fixture-target');
    }
    if(mode==='keyboard') {
      await page.getByLabel('Layout used in the game').selectOption('00000409');
      await page.getByRole('button',{name:'Capture key',exact:true}).click();
      await page.getByLabel('Key or named key',{exact:true}).press('Shift+KeyA');
      await expect(page.getByLabel('Key or named key',{exact:true})).toHaveValue('shift+KeyA');
    } else {
      await expect(page.locator('#layout-section')).toBeHidden();
      await setXbox(page,'A+RB');
      editor.data.ready=true; await writeFile(editor.fixture,JSON.stringify(editor.data));
    }
    await page.getByRole('button',{name:'Recheck dependencies'}).click();
    await expect(page.locator('#dependency-message')).toContainText('Ready for emulation');
    await page.getByRole('button',{name:'Save configuration'}).click();
    await expect(page.locator('#message')).toContainText('Saved. Run emulate.cmd to start');
    const saved=JSON.parse(await readFile(join(editor.root,'.local','config.json'),'utf8'));
    expect(saved.preferred_mode).toBe(mode);
    expect(saved.profiles[mode].layout).toBe(mode==='keyboard'?'00000409':null);
    await page.reload();
    await expect(page.getByLabel('Preferred mode')).toHaveValue(mode);
    expect(editor.external).toEqual([]);
  });
}

test('invalid mapping and active session preserve edits and return actionable errors', async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await page.route('**/save',route=>route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({message:'Choose Xbox button names.',field:'buttons:s1'})}));
  await setXbox(page,'LT');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#binding-error')).toContainText('Xbox button names');
  await expect(page.locator('#xbox-output-0')).toBeFocused();
  await expect(page.locator('#xbox-output-0')).toHaveAttribute('aria-invalid','true');
  await expect(page.locator('#xbox-output-0')).toHaveValue('LT');
  await page.unroute('**/save');
  await setXbox(page,'A');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await writeFile(join(editor.root,'.local','session.json'),JSON.stringify({nonce:'fixture'}));
  await setXbox(page,'B');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Stop emulation');
  const saved=JSON.parse(await readFile(join(editor.root,'.local','config.json'),'utf8'));
  expect(saved.profiles.xbox.buttons.s1).toBe('A');
});

test('diagram keyboard control, dirty-mode cancellation and responsive layout', async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  const marker=page.getByRole('button',{name:'Sidestick button 11',exact:true});
  await marker.focus(); await marker.press('Enter');
  await expect(page.getByLabel('Physical control or action')).toHaveValue('buttons:s11');
  await setXbox(page,'UP+Y');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.getByLabel('Preferred mode').selectOption('keyboard');
  await expect(page.getByLabel('Preferred mode')).toHaveValue('xbox');
  await page.setViewportSize({width:480,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/configuration-narrow.png',fullPage:true});
  await page.setViewportSize({width:1280,height:1000});
  await page.screenshot({path:'test-results/configuration-desktop.png',fullPage:true});
  expect(editor.external).toEqual([]);
});

test('cross-origin save is rejected', async({request,editor})=>{
  const response=await request.post(editor.url+'save',{headers:{Origin:'https://example.invalid'},data:{}});
  expect(response.status()).toBe(403);
});

test('live controls clear on disconnect and calibration persists independently',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  editor.data.input={available:true,state:{stick:{axes:[0,.5,0,0,0,0],buttons:[11],hat:[1,0]},quadrant:{axes:[-.8,0,0,0,0,0],buttons:[2],hat:[0,0]}}};
  await writeFile(editor.fixture,JSON.stringify(editor.data));
  await expect(page.locator('[data-control="s11"]')).toHaveClass(/live/);
  await expect(page.locator('#axis-preview')).toContainText('0.50');
  await page.locator('#calibration > summary').click();
  await page.getByLabel('roll input axis').selectOption('1');
  await page.getByLabel('Invert roll',{exact:true}).check();
  await page.getByLabel('Flight deadzone',{exact:true}).fill('.12');
  await page.getByLabel('Throttle center deadzone').fill('.2');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await page.getByLabel('Preferred mode').selectOption('target-xbox');
  await expect(page.getByLabel('Flight deadzone',{exact:true})).toHaveValue('0.04');
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await expect(page.getByLabel('Flight deadzone',{exact:true})).toHaveValue('0.12');
  editor.data.input={available:false,message:'Device disconnected; reconnect.'};await writeFile(editor.fixture,JSON.stringify(editor.data));
  await expect(page.locator('.control.live')).toHaveCount(0);
  await expect(page.locator('#axis-preview')).toBeEmpty();
  await expect(page.locator('#input-status')).toContainText('reconnect');
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'Reset this mode'}).click();
  await expect(page.getByLabel('Flight deadzone',{exact:true})).toHaveValue('0.04');
});

test('layout suggestion requires consent, other layouts and physical capture persist',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('keyboard');
  await page.getByRole('button',{name:'Use suggested Windows layout'}).click();
  await expect(page.getByLabel('Layout used in the game')).toHaveValue('0000040c');
  await page.getByLabel('Layout used in the game').selectOption('00000407');
  await page.getByRole('button',{name:'Capture key',exact:true}).click();
  await page.locator('#binding').dispatchEvent('keydown',{key:'Dead',code:'KeyA'});
  await expect(page.locator('#message')).toContainText('standard game key');
  await page.locator('#binding').press('Control+KeyZ');
  await expect(page.locator('#binding')).toHaveValue('ctrl+KeyZ');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  const saved=JSON.parse(await readFile(join(editor.root,'.local/config.json'),'utf8'));
  expect(saved.profiles.keyboard.layout).toBe('00000407');
  expect(saved.profiles.keyboard.buttons.s1).toEqual({code:'KeyZ',modifiers:['ctrl']});
});

test('failed save, dependency checks and initial loading all offer recovery',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await page.route('**/save',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({message:'Could not save configuration. Check folder permissions.'})}));
  await setXbox(page,'B');await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Your changes remain');
  await expect(page.locator('#xbox-output-0')).toHaveValue('B');
  await page.unroute('**/save');await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await page.route('**/dependencies',route=>route.fulfill({status:503,contentType:'application/json',body:'{"message":"Check unavailable"}'}));
  await page.getByRole('button',{name:'Recheck dependencies'}).click();
  await expect(page.locator('#dependency-message')).toContainText('failed');
  await page.unroute('**/dependencies');await page.getByRole('button',{name:'Recheck dependencies'}).click();
  await expect(page.locator('#dependencies')).toContainText('ViGEmBus driver');
  await page.route('**/state',route=>route.fulfill({status:503,body:'{}'}));await page.reload();
  await expect(page.locator('#load-error')).toContainText('Reopen configure.cmd');
  await page.unroute('**/state');await page.reload();
  await expect(page.getByLabel('Preferred mode')).toHaveValue('xbox');
});

test('keyboard focus, text contrast and 320px layout remain usable',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await page.getByRole('button',{name:'Quadrant',exact:true}).click();
  const marker=page.getByRole('button',{name:'Quadrant button 2',exact:true});
  await marker.focus();await marker.press('Space');
  await expect(page.getByLabel('Physical control or action')).toHaveValue('buttons:q2');
  await expect(page.locator('#xbox-output-0')).toBeFocused();
  const ratios=await page.evaluate(()=>{
    const luminance=color=>{const rgb=color.match(/[\d.]+/g).slice(0,3).map(v=>Number(v)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
    return [...document.querySelectorAll('h1,h2,h3,p,label,button,select,input,strong')].filter(el=>el.getClientRects().length && !el.disabled && el.textContent.trim()).map(el=>{
      let ancestor=el,background='rgba(0, 0, 0, 0)';
      while(ancestor && background==='rgba(0, 0, 0, 0)'){background=getComputedStyle(ancestor).backgroundColor;ancestor=ancestor.parentElement;}
      const a=luminance(getComputedStyle(el).color),b=luminance(background);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    });
  });
  expect(Math.min(...ratios)).toBeGreaterThanOrEqual(4.5);
  await page.setViewportSize({width:320,height:800});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await expect(page.getByRole('button',{name:'Save configuration'})).toBeVisible();
  expect(editor.external).toEqual([]);
});

test('a narrow binding edit can be saved without opening diagrams or calibration',async({page,editor})=>{
  await page.setViewportSize({width:390,height:844});await page.reload();
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await expect(page.locator('#photo-panel')).not.toHaveAttribute('open','');
  await expect(page.locator('#calibration')).not.toHaveAttribute('open','');
  const binding=await page.locator('#xbox-output-0').boundingBox();
  const save=await page.locator('#save').boundingBox();
  expect(save.y-binding.y).toBeLessThan(400);
  await setXbox(page,'RB');await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await page.locator('#overview > summary').click();
  await expect(page.locator('[data-mapping="buttons:s1"]')).toContainText('RB');
  await page.getByRole('button',{name:'Edit Quadrant 2',exact:true}).click();
  await expect(page.locator('#control')).toHaveValue('buttons:q2');
  await expect(page.locator('#xbox-output-0')).toBeFocused();
  expect(editor.external).toEqual([]);
});

test('numeric errors reveal calibration and associate the remedy with its field',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await page.locator('#calibration > summary').click();
  await page.getByLabel('Input frequency · Hz',{exact:true}).fill('501');
  await page.locator('#calibration > summary').click();
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#poll_hz')).toBeFocused();
  await expect(page.locator('#poll_hz-error')).toContainText('10 to 500');
  await expect(page.locator('#poll_hz')).toHaveAttribute('aria-invalid','true');
  await page.getByLabel('Input frequency · Hz',{exact:true}).fill('125');
  await expect(page.locator('#poll_hz-error')).toBeEmpty();
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
});

async function setXbox(page, value) {
  const rows=page.locator('#xbox-rows .xbox-output-row');
  while(await rows.count()>1) await rows.last().getByRole('button').click();
  for(const [index,part] of value.split('+').entries()) {
    if(index) await page.getByRole('button',{name:'Add button',exact:true}).click();
    await page.getByLabel('Xbox button '+(index+1),{exact:true}).selectOption(part);
  }
}

test('both binding editors remain usable at a 200% zoom-equivalent viewport',async({browser,editor})=>{
  // A 1280px display at 200% zoom exposes 640 CSS pixels with a 2x scale.
  const context=await browser.newContext({viewport:{width:640,height:500},deviceScaleFactor:2});
  const page=await context.newPage();
  page.on('request',request=>{if(!request.url().startsWith(editor.url) && !request.url().startsWith('data:')) editor.external.push(request.url());});
  await page.goto(editor.url);
  try {
  for(const mode of ['xbox','keyboard']) {
    await page.getByLabel('Preferred mode').selectOption(mode);
    const field=page.locator(mode==='xbox'?'#xbox-output-0':'#binding');
    await field.focus();await expect(field).toBeFocused();
    await expect(field).toBeInViewport();
    await expect(page.locator('#save')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:'test-results/'+mode+'-zoom.png',fullPage:true});
  }
  } finally { await context.close(); }
  expect(editor.external).toEqual([]);
});
test('Xbox dropdown combinations, triggers and removal save without changing profile format',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('xbox');
  await expect(page.locator('#keyboard-binding')).toBeHidden();
  await expect(page.locator('#xbox-output-0 option[value="LT"]')).toHaveText('LT (Decelerate)');
  await setXbox(page,'LT+RT+A');
  await expect(page.locator('#xbox-output-2 option[value="LT"]')).toBeDisabled();
  await page.getByRole('button',{name:'Add button',exact:true}).click();
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  let saved=JSON.parse(await readFile(join(editor.root,'.local/config.json'),'utf8'));
  expect(saved.profiles.xbox.version).toBe(1);expect(saved.profiles.xbox.buttons.s1).toBe('LT+RT+A');
  await page.reload();await expect(page.locator('#xbox-output-2')).toHaveValue('A');
  await setXbox(page,'');await expect(page.locator('#xbox-output-0')).toHaveValue('');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  saved=JSON.parse(await readFile(join(editor.root,'.local/config.json'),'utf8'));
  expect(saved.profiles.xbox.buttons.s1).toBe('');expect(editor.external).toEqual([]);
});

test('keyboard capture accepts standalone modifiers and extended keys with honest action hints',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('keyboard');
  await expect(page.getByLabel('Default AC8 PC action')).toHaveAttribute('readonly','');
  await expect(page.getByLabel('Default AC8 PC action')).toHaveValue('Choose a keyboard layout to identify this key.');
  await page.getByLabel('Layout used in the game').selectOption('00000409');
  await expect(page.getByLabel('Default AC8 PC action')).toHaveValue('Fire machine gun');
  for(const key of ['ControlLeft','ShiftRight','AltLeft','PrintScreen','F13','F24']) {
    await page.getByRole('button',{name:'Capture key',exact:true}).click();
    if (key==='F13' || key==='F24') await page.locator('#binding').dispatchEvent('keydown',{key,code:key});
    else await page.locator('#binding').press(key);
    await expect(page.locator('#binding')).toHaveValue(key);
  }
  await page.getByRole('button',{name:'Capture key',exact:true}).click();
  await page.locator('#binding').press('Control+KeyA');
  await expect(page.locator('#binding')).toHaveValue('ctrl+KeyA');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  const saved=JSON.parse(await readFile(join(editor.root,'.local/config.json'),'utf8'));
  expect(saved.profiles.keyboard.buttons.s1).toEqual({code:'KeyA',modifiers:['ctrl']});
  await page.screenshot({path:'test-results/keyboard-desktop.png',fullPage:true});
  await page.setViewportSize({width:320,height:800});
  await page.screenshot({path:'test-results/keyboard-narrow.png',fullPage:true});
  expect(await page.getByLabel('Default AC8 PC action').evaluate(input=>input.scrollHeight<=input.clientHeight)).toBe(true);
  await page.locator('#binding').fill('');
  await expect(page.getByLabel('Default AC8 PC action')).toHaveValue('Unassigned.');
  await page.setViewportSize({width:320,height:800});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(editor.external).toEqual([]);
});

test('supplied actions follow physical QWERTY positions on AZERTY and distinguish number keys',async({page,editor})=>{
  await page.getByLabel('Preferred mode').selectOption('keyboard');
  await expect(page.locator('#binding-help')).toContainText('physical US QWERTY');
  await page.getByLabel('Layout used in the game').selectOption('0000040c');
  await page.locator('#control').selectOption('keys:yaw_left');
  await expect(page.locator('#binding')).toHaveValue('KeyQ');
  await expect(page.locator('#key-action')).toHaveValue('Yaw left');
  await page.locator('#binding').fill('a');await expect(page.locator('#key-action')).toHaveValue('Yaw left');
  await page.locator('#binding').fill('q');await expect(page.locator('#key-action')).toHaveValue('Turn left / Roll left');
  for(const [key,action] of [['Digit7','Camera up'],['Numpad8','Camera up'],['Digit8','Camera down'],['ControlLeft','Decelerate']]) {
    await page.getByRole('button',{name:'Capture key',exact:true}).click();await page.locator('#binding').press(key);
    await expect(page.locator('#key-action')).toHaveValue(action);
  }
  await page.locator('#binding').fill('7');
  await expect(page.locator('#key-action')).toHaveValue('No default action listed; set this action manually in game.');
  await page.locator('#binding').fill('F24');
  await expect(page.locator('#key-action')).toHaveValue('No default action listed; set this action manually in game.');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/ac8-keyboard-narrow.png',fullPage:true});
  expect(editor.external).toEqual([]);
});

test('legacy unconfigured profiles stay unchanged until an explicit reset and save',async({page,editor})=>{
  const profiles=JSON.parse(await readFile('tests/fixtures/profiles.json','utf8'));
  const saved={version:1,preferred_mode:'xbox',target_path:'',profiles};
  const path=join(editor.root,'.local/config.json'),raw=JSON.stringify(saved);
  await mkdir(join(editor.root,'.local'),{recursive:true});await writeFile(path,raw);
  await page.reload();await page.getByLabel('Preferred mode').selectOption('keyboard');
  await expect(page.locator('#binding')).toHaveValue('Space');
  expect(await readFile(path,'utf8')).toBe(raw);
  page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Reset this mode',exact:true}).click();
  await expect(page.locator('#binding')).toHaveValue('KeyJ');
  await page.getByLabel('Layout used in the game').selectOption('0000040c');
  await expect(page.locator('#key-action')).toHaveValue('Fire machine gun');
  await page.locator('#control').selectOption('keys:brake');await expect(page.locator('#binding')).toHaveValue('ControlLeft');
  await expect(page.locator('#key-action')).toHaveValue('Decelerate');
  await page.locator('#control').selectOption('buttons:s10');await expect(page.locator('#binding')).toHaveValue('');
  await page.locator('#control').selectOption('buttons:s15');await expect(page.locator('#binding')).toHaveValue('');
  expect(await readFile(path,'utf8')).toBe(raw);
  await page.getByRole('button',{name:'Save configuration'}).click();await expect(page.locator('#message')).toContainText('Saved.');
  const updated=JSON.parse(await readFile(path,'utf8'));
  expect(updated.profiles.keyboard.keys.yaw_left).toEqual({code:'KeyQ',modifiers:[]});
  expect(updated.profiles.xbox).toEqual(profiles.xbox);
  expect(await readFile(join(editor.root,'.local/config.previous.json'),'utf8')).toBe(raw);
  expect(editor.external).toEqual([]);
});
