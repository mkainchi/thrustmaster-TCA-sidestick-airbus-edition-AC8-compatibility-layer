import {request, bindingLabel, capturedKey} from './logic.js';

export async function start(doc, win, fetcher) {
  const $ = id => doc.getElementById(id);
  const base = win.location.pathname;
  const api = (route, data) => request(fetcher, base, route, data);
  let state, mode, profile, dirty = false, busy = false, armed = false;
  let pressed = null, polling = false, inputGeneration = 0, closed = false;
  const numeric = ['deadzone', 'throttle_deadzone', 'yaw_threshold', 'camera_strength', 'high_g_button', 'poll_hz'];
  const keyboard = () => mode === 'keyboard';
  const descriptions = {
    keyboard: 'Keyboard keys through TARGET. Choose the installed layout used by your game.',
    xbox: 'Xbox controller output directly from both devices. TARGET is not required.',
    'target-xbox': 'Xbox output through TARGET Combined. Use direct input for ordinary Xbox-controller play; use this route when your setup needs TARGET to combine the devices. Requires TARGET and ViGEmBus.'
  };
  const xboxButtons = ['A','B','X','Y','LB','RB','L3','R3','START','BACK','UP','DOWN','LEFT','RIGHT'];
  const controlName = (group, key) => group === 'keys' ? key.replaceAll('_', ' ') : (key.startsWith('s') ? 'Sidestick ' : 'Quadrant ') + key.slice(1);
  function message(text, error = false) {
    $('message').textContent = text;
    $('message').className = error ? 'error' : '';
  }
  function refreshSave() {
    $('save').disabled = busy || state.active || !mode || (keyboard() && !profile.layout);
    $('revert').disabled = busy || !dirty;
  }
  function clearError(id) {
    $(id).removeAttribute('aria-invalid');
    $(id + '-error').textContent = '';
  }
  function clearErrors() {
    for (const field of doc.querySelectorAll('[aria-invalid]')) clearError(field.id);
  }
  function fieldError(field, text) {
    let id = field;
    if (/^(buttons|keys):/.test(field)) { $('control').value = field; selection(); id = 'binding'; }
    else id = field.replace(':', '-');
    const input = $(id);
    if (!input) return;
    input.setAttribute('aria-invalid', 'true');
    $(id + '-error').textContent = text;
    if ($('calibration').contains(input)) $('calibration').open = true;
    input.focus();
  }
  function changed(id) {
    dirty = true;
    if (id) clearError(id);
    refreshSave(); refreshOverview(); message('Unsaved changes.');
  }
  function refreshOverview() {
    for (const row of doc.querySelectorAll('[data-mapping]')) {
      const [group, key] = row.dataset.mapping.split(':');
      const binding = bindingLabel(profile[group][key]);
      row.querySelector('.mapping-output').textContent = group === 'buttons' && key === 's' + profile.high_g_button ? (binding ? binding + ' + ' : '') + 'High-G override' : binding || 'Unassigned';
    }
  }
  function overview() {
    $('mapping-overview').replaceChildren();
    const groups = [['Sidestick', 'buttons', Object.keys(profile.buttons).filter(key => key.startsWith('s'))],
      ['Quadrant', 'buttons', Object.keys(profile.buttons).filter(key => key.startsWith('q'))],
      ...(keyboard() ? [['Flight and camera actions', 'keys', Object.keys(profile.keys)]] : [])];
    for (const [name, group, keys] of groups) {
      const table = doc.createElement('table'), caption = doc.createElement('caption');
      caption.textContent = name; table.append(caption);
      const body = doc.createElement('tbody'); table.append(body);
      for (const key of keys) {
        const row = doc.createElement('tr'), label = doc.createElement('th'), output = doc.createElement('td'), button = doc.createElement('button');
        row.dataset.mapping = group + ':' + key; label.scope = 'row';
        button.type = 'button'; button.textContent = 'Edit ' + controlName(group, key);
        button.onclick = () => { $('control').value = group + ':' + key; selection(); $('binding').focus(); };
        label.append(button); output.className = 'mapping-output'; row.append(label, output); body.append(row);
      }
      $('mapping-overview').append(table);
    }
    refreshOverview();
  }
  function selection() {
    $('control-status').textContent = '';
    const selected = $('control').value;
    const [group, key] = selected.split(':');
    clearError('binding');
    $('binding').value = bindingLabel(profile[group][key]);
    $('binding-label').textContent = keyboard() ? 'Key or named key' : 'Xbox button or combination';
    $('binding-help').textContent = keyboard() ? 'Type a character or named key (Space, Enter, ArrowLeft, F1), or capture a physical key. Leave a button blank to unassign it.' : 'Face: A, B, X, Y. Shoulders: LB, RB. Stick clicks: L3, R3. Menu: START, BACK. D-pad: UP, DOWN, LEFT, RIGHT. Join names with +, or leave blank.';
    $('special-binding').textContent = group === 'buttons' && key === 's' + profile.high_g_button ? 'This button holds acceleration and braking together. Its High-G override takes priority over throttle input; an assigned button binding also remains active. Change or disable High-G in calibration.' : '';
    const quadrant = group === 'buttons' && key.startsWith('q');
    $('stick-photo').hidden = quadrant; $('quadrant-photo').hidden = !quadrant;
    $('show-stick').setAttribute('aria-pressed', String(!quadrant)); $('show-quadrant').setAttribute('aria-pressed', String(quadrant));
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
      const missing = items.filter(item => !item.ready).length;
      $('dependency-summary').textContent = missing ? '· ' + missing + ' need attention' : '· Ready';
      $('dependency-panel').open = missing > 0;
    } catch (error) { $('dependency-panel').open = true; $('dependency-summary').textContent = '· Check failed'; $('dependency-message').textContent = 'Dependency check failed. Reopen configure.cmd or recheck. ' + error.message; }
    finally { $('recheck').disabled = false; }
  }
  function render() {
    $('workspace').hidden = !mode;
    if (!mode) return;
    clearErrors();
    $('mode-description').textContent = descriptions[mode] + ' Your mappings stay on this computer.';
    $('layout-section').hidden = !keyboard();
    $('target-field').hidden = mode === 'xbox';
    $('capture').hidden = !keyboard();
    $('layout').value = profile.layout || '';
    $('control').replaceChildren();
    for (const [group, bindings] of Object.entries({buttons: profile.buttons, ...(keyboard() ? {keys: profile.keys} : {})})) {
      const optionGroup = doc.createElement('optgroup'); optionGroup.label = group === 'buttons' ? 'Physical buttons and detents' : 'Flight and camera actions';
      for (const key of Object.keys(bindings)) {
        const option = doc.createElement('option'); option.value = group + ':' + key;
        option.textContent = controlName(group, key);
        optionGroup.append(option);
      }
      $('control').append(optionGroup);
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
        const error = doc.createElement('p'); error.id = field.id + '-error'; error.className = 'field-error';
        field.setAttribute('aria-describedby', error.id);
        label.htmlFor = field.id;
        const wrapper = doc.createElement('div'); wrapper.append(label, field, error); holder.append(wrapper);
        field.onchange = () => { profile[group][key] = group === 'axes' ? Number(field.value) : field.checked; changed(field.id); };
      }
    }
    for (const name of numeric) $(name).value = profile[name];
    $('camera_strength').disabled = keyboard();
    $('camera-setting').hidden = keyboard();
    overview();
    refreshSave();
  }
  async function chooseMode() {
    const next = $('mode').value;
    if (dirty && !win.confirm('Discard unsaved changes in this mode?')) { $('mode').value = mode; return; }
    mode = next; dirty = false;
    inputGeneration++; clearInput();
    if (mode) profile = structuredClone(state.saved.profiles[mode]);
    render();
    if (mode) { await recheck(); message(state.active ? 'Stop emulation before saving changes.' : 'Review mappings, then save this mode.'); }
    else $('mode-description').textContent = 'Choose the output your game accepts. Your mappings stay on this computer.';
  }
  async function poll() {
    if (!mode || polling || closed) return;
    polling = true;
    const generation = inputGeneration;
    try {
      const data = await api('input');
      if (closed || generation !== inputGeneration) return;
      if (!data.available) { clearInput(); $('input-status').textContent = data.message; return; }
      $('input-status').textContent = 'Live input · move a lever or press a button.';
      for (const element of doc.querySelectorAll('[data-control]')) {
        const key = element.dataset.control, device = key[0] === 's' ? 'stick' : 'quadrant';
        element.classList.toggle('live', data.state[device].buttons.includes(Number(key.slice(1))));
      }
      const down = new Set(['s', 'q'].flatMap(prefix => data.state[prefix === 's' ? 'stick' : 'quadrant'].buttons.map(number => prefix + number)).filter(key => Object.hasOwn(profile.buttons, key)));
      const fresh = pressed === null ? [] : [...down].filter(key => !pressed.has(key));
      pressed = down;
      if (fresh.length && !busy && !armed && !doc.activeElement.matches('input, select:not(#mode), textarea')) {
        const preferred = $('quadrant-photo').hidden ? 's' : 'q';
        fresh.sort((a, b) => Number(b.startsWith(preferred)) - Number(a.startsWith(preferred)) || Number(a.slice(1)) - Number(b.slice(1)));
        $('control').value = 'buttons:' + fresh[0]; selection();
        $('control-status').textContent = controlName('buttons', fresh[0]) + ' selected from live input.';
      }
      $('axis-preview').textContent = 'Stick: ' + data.state.stick.axes.map(v => v.toFixed(2)).join(' / ') + ' · Throttle: ' + data.state.quadrant.axes.map(v => v.toFixed(2)).join(' / ');
    } catch {
      if (!closed && generation === inputGeneration) { clearInput(); $('input-status').textContent = 'Live input unavailable. Reconnect devices or reopen configure.cmd.'; }
    } finally { polling = false; }
  }
  function clearInput() {
    pressed = null;
    $('control-status').textContent = '';
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
    $('target-path').oninput = () => changed();
    $('control').onchange = selection;
    $('layout').onchange = () => { profile.layout = $('layout').value; changed('layout'); };
    $('use-layout').onclick = () => {
      if (!suggestion) { const text = 'Windows layout unavailable. Choose a layout from the list.'; message(text, true); fieldError('layout', text); return; }
      $('layout').value = suggestion.id; $('layout').dispatchEvent(new win.Event('change'));
    };
    for (const element of doc.querySelectorAll('[data-control]')) {
      const select = () => { $('control').value = 'buttons:' + element.dataset.control; selection(); $('binding').focus(); };
      element.onclick = select;
      element.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } };
    }
    $('binding').oninput = () => {
      const [group, key] = $('control').value.split(':'); profile[group][key] = $('binding').value;
      armed = false; $('capture').textContent = 'Capture key'; changed('binding');
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
        profile[group][key] = binding; $('binding').value = bindingLabel(binding); armed = false; $('capture').textContent = 'Capture key'; changed('binding');
      } catch (error) { fieldError('binding', error.message); message(error.message, true); }
    };
    for (const name of numeric) $(name).oninput = () => { profile[name] = Number($(name).value); changed(name); selection(); };
    $('revert').onclick = () => {
      if (win.confirm('Discard changes and restore your last saved mappings?')) { profile = structuredClone(state.saved.profiles[mode]); $('target-path').value = state.saved.target_path; dirty = false; render(); message('Restored your saved mappings.'); }
    };
    $('reset').onclick = () => { if (win.confirm('Reset mappings for this mode?')) { profile = structuredClone(state.defaults[mode]); render(); changed(); } };
    $('save').onclick = async () => {
      clearErrors();
      if (!keyboard()) {
        for (const [key, binding] of Object.entries(profile.buttons)) {
          if (binding && binding.split('+').some(name => !xboxButtons.includes(name))) {
            const text = 'Use the Xbox button names shown below the field, joined with +, or leave it blank.';
            fieldError('buttons:' + key, text); message(text, true); return;
          }
        }
      }
      for (const name of numeric) {
        if (!$(name).disabled && !$(name).checkValidity()) {
          const text = doc.querySelector('label[for="' + name + '"]').textContent + ': enter a number from ' + $(name).min + ' to ' + $(name).max + ' in steps of ' + $(name).step + '.';
          fieldError(name, text); message(text, true); return;
        }
      }
      busy = true; refreshSave(); message('Saving…');
      const fields = [...doc.querySelectorAll('input, select, button')];
      const disabled = fields.map(field => field.disabled);
      for (const field of fields) field.disabled = true;
      let validation;
      try {
        const result = await api('save', {mode, profile, target_path: $('target-path').value});
        state.saved.profiles[mode] = structuredClone(profile); state.saved.preferred_mode = mode;
        state.saved.target_path = $('target-path').value;
        dirty = false; message(result.message);
      } catch (error) { validation = error; message(error.message + ' Your changes remain in this page; correct them or retry.', true); }
      finally { fields.forEach((field, index) => { field.disabled = disabled[index]; }); busy = false; refreshSave(); if (validation?.field) fieldError(validation.field, validation.message); }
    };
    $('show-stick').onclick = () => { $('control').value = 'buttons:s1'; selection(); };
    $('show-quadrant').onclick = () => { $('control').value = 'buttons:q1'; selection(); };
    $('handedness').onchange = () => { doc.querySelector('.sidestick-photo').dataset.hand = $('handedness').value; };
    $('photo-panel').open = win.innerWidth >= 900;
    for (const image of doc.querySelectorAll('.photo-frame img')) {
      const frame = image.parentElement, notice = frame.nextElementSibling;
      image.onerror = () => { frame.hidden = true; notice.hidden = false; };
      image.onload = () => { frame.hidden = false; notice.hidden = true; };
    }
    await chooseMode();
  } catch { $('load-error').textContent = 'Cannot load configuration. Reopen configure.cmd to restart the local editor.'; return null; }
  const unload = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
  win.addEventListener('beforeunload', unload);
  const timer = win.setInterval(poll, 50);
  return {close() { closed = true; win.clearInterval(timer); win.removeEventListener('beforeunload', unload); }, poll};
}
