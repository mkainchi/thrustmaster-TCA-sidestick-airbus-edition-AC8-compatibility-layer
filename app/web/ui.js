import {request, bindingLabel, capturedKey, modeLabel} from './logic.js';

export async function start(doc, win, fetcher) {
  const $ = id => doc.getElementById(id);
  const base = win.location.pathname;
  const api = (route, data) => request(fetcher, base, route, data);
  let state, mode, profile, dirty = false, busy = false, armed = false;
  const numeric = ['deadzone', 'throttle_deadzone', 'yaw_threshold', 'camera_strength', 'high_g_button', 'poll_hz'];
  const keyboard = () => mode === 'keyboard';
  function message(text, error = false) {
    $('message').textContent = text;
    $('message').className = error ? 'error' : '';
  }
  function refreshSave() {
    $('save').disabled = busy || state.active || !mode || (keyboard() && !profile.layout);
  }
  function changed() { dirty = true; refreshSave(); message('Unsaved changes.'); }
  function selection() {
    const selected = $('control').value;
    const [group, key] = selected.split(':');
    $('binding').value = bindingLabel(profile[group][key]);
    $('binding-label').textContent = keyboard() ? 'Key or named key' : 'Xbox button or combination';
    $('binding-help').textContent = keyboard() ? 'Type a character or named key, or capture a physical key. Leave a button blank to unassign it.' : 'A, B, X, Y, LB, RB, L3, R3, START, BACK, UP, DOWN, LEFT, RIGHT. Join buttons with +, or leave blank.';
    armed = false; $('capture').textContent = 'Capture key';
    for (const element of doc.querySelectorAll('[data-control]')) {
      element.setAttribute('aria-pressed', String(selected === 'buttons:' + element.dataset.control));
    }
  }
  async function recheck() {
    $('recheck').disabled = true;
    $('dependency-message').textContent = 'Checking dependencies…';
    try {
      const items = await api('dependencies', {mode, target_path: $('target-path').value});
      $('dependencies').replaceChildren();
      for (const item of items) {
        const li = doc.createElement('li'), title = doc.createElement('strong');
        title.textContent = item.label + ' · ' + (item.ready ? 'Ready' : 'Needs attention');
        li.append(title);
        if (!item.ready) {
          const help = doc.createElement('p'); help.textContent = item.remedy; li.append(help);
          if (item.url) {
            const link = doc.createElement('a'); link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
            link.textContent = 'Official installation instructions'; li.append(link);
          }
        }
        if (item.id === 'target' && item.ready) $('target-path').value = item.path;
        $('dependencies').append(li);
      }
      $('dependency-message').textContent = items.every(item => item.ready) ? 'Ready for emulation after saving.' : 'You can save mappings now. Resolve missing dependencies before emulation.';
    } catch (error) { $('dependency-message').textContent = 'Dependency check failed. Reopen configure.cmd or recheck. ' + error.message; }
    finally { $('recheck').disabled = false; }
  }
  function render() {
    $('workspace').hidden = !mode;
    if (!mode) return;
    $('mode-description').textContent = modeLabel(mode) + ' output. Your mappings stay on this computer.';
    $('layout-section').hidden = !keyboard();
    $('target-field').hidden = mode === 'xbox';
    $('capture').hidden = !keyboard();
    $('layout').value = profile.layout || '';
    $('control').replaceChildren();
    for (const [group, bindings] of Object.entries({buttons: profile.buttons, ...(keyboard() ? {keys: profile.keys} : {})})) {
      for (const key of Object.keys(bindings)) {
        const option = doc.createElement('option'); option.value = group + ':' + key;
        option.textContent = group === 'keys' ? key.replaceAll('_', ' ') : (key.startsWith('s') ? 'Sidestick ' : 'Quadrant ') + key.slice(1);
        $('control').append(option);
      }
    }
    selection();
    for (const [group, fields] of Object.entries({axes: profile.axes, invert: profile.invert})) {
      const holder = $(group === 'axes' ? 'axis-fields' : 'invert-fields'); holder.replaceChildren();
      for (const [key, value] of Object.entries(fields)) {
        const label = doc.createElement('label'), field = doc.createElement(group === 'axes' ? 'select' : 'input');
        field.id = group + '-' + key;
        if (group === 'axes') {
          for (const [index, name] of ['X', 'Y', 'Z', 'R (twist)', 'U', 'V'].entries()) {
            const option = doc.createElement('option'); option.value = String(index); option.textContent = index + ' · ' + name; field.append(option);
          }
          field.value = String(value); label.textContent = key + ' input axis';
        } else { field.type = 'checkbox'; field.checked = value; label.textContent = 'Invert ' + key; }
        label.htmlFor = field.id; holder.append(label, field);
        field.onchange = () => { profile[group][key] = group === 'axes' ? Number(field.value) : field.checked; changed(); };
      }
    }
    for (const name of numeric) $(name).value = profile[name];
    $('camera_strength').disabled = keyboard();
    refreshSave();
  }
  async function chooseMode() {
    const next = $('mode').value;
    if (dirty && !win.confirm('Discard unsaved changes in this mode?')) { $('mode').value = mode; return; }
    mode = next; dirty = false;
    if (mode) profile = structuredClone(state.saved.profiles[mode]);
    render();
    if (mode) { await recheck(); message(state.active ? 'Stop emulation before saving changes.' : 'Review mappings, then save this mode.'); }
  }
  async function poll() {
    if (!mode) return;
    try {
      const data = await api('input');
      if (!data.available) { clearInput(); $('input-status').textContent = data.message; return; }
      $('input-status').textContent = 'Live input · move a lever or press a button.';
      for (const element of doc.querySelectorAll('[data-control]')) {
        const key = element.dataset.control, device = key[0] === 's' ? 'stick' : 'quadrant';
        element.classList.toggle('live', data.state[device].buttons.includes(Number(key.slice(1))));
      }
      $('axis-preview').textContent = 'Stick: ' + data.state.stick.axes.map(v => v.toFixed(2)).join(' / ') + ' · Throttle: ' + data.state.quadrant.axes.map(v => v.toFixed(2)).join(' / ');
    } catch { clearInput(); $('input-status').textContent = 'Live input unavailable. Reconnect devices or reopen configure.cmd.'; }
  }
  function clearInput() {
    for (const element of doc.querySelectorAll('.control.live')) element.classList.remove('live');
    $('axis-preview').textContent = '';
  }
  try {
    state = await api('state');
    for (const item of state.layouts) {
      const option = doc.createElement('option'); option.value = item.id; option.textContent = item.label; $('layout').append(option);
    }
    const suggestion = state.layouts.find(item => item.id === state.suggested);
    $('layout-help').textContent = suggestion ? 'Windows suggests ' + suggestion.label + '. Confirm the layout used in your game.' : 'Choose an installed Windows layout. No layout is assumed.';
    $('target-path').value = state.saved.target_path;
    $('mode').value = state.saved.preferred_mode || '';
    $('mode').onchange = chooseMode;
    $('recheck').onclick = recheck;
    $('target-path').oninput = changed;
    $('control').onchange = selection;
    $('layout').onchange = () => { profile.layout = $('layout').value; changed(); };
    $('use-layout').onclick = () => {
      if (!suggestion) { message('Windows layout unavailable. Choose a layout from the list.', true); return; }
      $('layout').value = suggestion.id; $('layout').dispatchEvent(new win.Event('change'));
    };
    for (const element of doc.querySelectorAll('[data-control]')) {
      const select = () => { $('control').value = 'buttons:' + element.dataset.control; selection(); $('binding').focus(); };
      element.onclick = select;
      element.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } };
    }
    $('binding').oninput = () => {
      const [group, key] = $('control').value.split(':'); profile[group][key] = $('binding').value;
      armed = false; $('capture').textContent = 'Capture key'; changed();
    };
    $('capture').onclick = () => { armed = true; $('capture').textContent = 'Press key…'; $('binding').focus(); };
    $('binding').onblur = () => { armed = false; $('capture').textContent = 'Capture key'; };
    $('binding').onkeydown = event => {
      if (!armed) return;
      event.preventDefault();
      try {
        const binding = capturedKey(event);
        if (binding === null) return;
        const [group, key] = $('control').value.split(':');
        profile[group][key] = binding; $('binding').value = bindingLabel(binding); armed = false; $('capture').textContent = 'Capture key'; changed();
      } catch (error) { message(error.message, true); }
    };
    for (const name of numeric) $(name).oninput = () => { profile[name] = Number($(name).value); changed(); };
    $('reset').onclick = () => { if (win.confirm('Reset mappings for this mode?')) { profile = structuredClone(state.defaults[mode]); render(); changed(); } };
    $('save').onclick = async () => {
      busy = true; refreshSave(); message('Saving…');
      const fields = [...doc.querySelectorAll('input, select, button')];
      const disabled = fields.map(field => field.disabled);
      for (const field of fields) field.disabled = true;
      try {
        const result = await api('save', {mode, profile, target_path: $('target-path').value});
        state.saved.profiles[mode] = structuredClone(profile); state.saved.preferred_mode = mode;
        dirty = false; message(result.message);
      } catch (error) { message(error.message + ' Your changes remain in this page; correct them or retry.', true); }
      finally { fields.forEach((field, index) => { field.disabled = disabled[index]; }); busy = false; refreshSave(); }
    };
    await chooseMode();
  } catch { $('load-error').textContent = 'Cannot load configuration. Reopen configure.cmd to restart the local editor.'; return null; }
  const unload = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
  win.addEventListener('beforeunload', unload);
  const timer = win.setInterval(poll, 400);
  return {close() { win.clearInterval(timer); win.removeEventListener('beforeunload', unload); }, poll};
}
