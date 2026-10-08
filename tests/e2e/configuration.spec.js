import {test as base, expect} from '@playwright/test';
import {mkdtemp, writeFile, readFile, rm, mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';

const test = base.extend({editor: async({page}, use) => {
  const root = await mkdtemp(join(tmpdir(), 'tca-e2e-'));
  const fixture = join(root, 'fixture.json');
  const data = {layouts: [{id:'00000409',label:'QWERTY · English'}, {id:'0000040c',label:'AZERTY · French'}, {id:'00000407',label:'QWERTZ · German'}], suggested:'0000040c', ready:false};
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
      await page.getByLabel('Xbox button or combination').fill('A+RB');
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
  await page.getByLabel('Xbox button or combination').fill('NOT_A_BUTTON');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#binding-error')).toContainText('Xbox button names');
  await expect(page.locator('#binding')).toBeFocused();
  await expect(page.locator('#binding')).toHaveAttribute('aria-invalid','true');
  await expect(page.getByLabel('Xbox button or combination')).toHaveValue('NOT_A_BUTTON');
  await page.getByLabel('Xbox button or combination').fill('A');
  await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await writeFile(join(editor.root,'.local','session.json'),JSON.stringify({nonce:'fixture'}));
  await page.getByLabel('Xbox button or combination').fill('B');
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
  await page.getByLabel('Xbox button or combination').fill('UP+Y');
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
  await page.locator('#binding').fill('B');await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Your changes remain');
  await expect(page.locator('#binding')).toHaveValue('B');
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
  await expect(page.locator('#binding')).toBeFocused();
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
  const binding=await page.locator('#binding').boundingBox();
  const save=await page.locator('#save').boundingBox();
  expect(save.y-binding.y).toBeLessThan(400);
  await page.locator('#binding').fill('RB');await page.getByRole('button',{name:'Save configuration'}).click();
  await expect(page.locator('#message')).toContainText('Saved.');
  await page.locator('#overview > summary').click();
  await expect(page.locator('[data-mapping="buttons:s1"]')).toContainText('RB');
  await page.getByRole('button',{name:'Edit Quadrant 2',exact:true}).click();
  await expect(page.locator('#control')).toHaveValue('buttons:q2');
  await expect(page.locator('#binding')).toBeFocused();
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
