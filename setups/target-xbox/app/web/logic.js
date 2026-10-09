export const labels = {keyboard: 'Keyboard', xbox: 'Xbox', 'target-xbox': 'TARGET → Xbox'};
export const modeLabel = mode => labels[mode];
export const bindingLabel = binding => typeof binding === 'string' ? binding : [...binding.modifiers, binding.code].join('+');

export function capturedKey(event, released = false) {
  if (event.metaKey || event.code.startsWith('Meta') || event.isComposing || event.key === 'Dead') {
    throw Error('Choose a standard game key; system shortcuts and text composition are unsupported.');
  }
  if (/^(Shift|Control|Alt)(Left|Right)$/.test(event.code)) return released ? {code: event.code, modifiers: []} : null;
  if (!/^(Key[A-Z]|Digit[0-9]|F([1-9]|1[0-9]|2[0-4])|Numpad([0-9]|Divide|Multiply|Subtract|Add|Enter|Decimal))$/.test(event.code) &&
      !['Enter','Escape','Backspace','Tab','Space','Minus','Equal','BracketLeft','BracketRight','Backslash','Semicolon','Quote','Backquote','Comma','Period','Slash','CapsLock','PrintScreen','ScrollLock','Pause','Insert','Home','PageUp','Delete','End','PageDown','ArrowRight','ArrowLeft','ArrowDown','ArrowUp','NumLock','IntlBackslash','ContextMenu'].includes(event.code)) {
    throw Error('Unsupported physical key. Use a standard key or a character binding.');
  }
  const modifiers = [];
  if (event.getModifierState('AltGraph')) modifiers.push('altgr');
  else {
    if (event.ctrlKey) modifiers.push('ctrl');
    if (event.altKey) modifiers.push('alt');
  }
  if (event.shiftKey) modifiers.push('shift');
  return {code: event.code, modifiers};
}

export async function request(fetcher, base, route, payload) {
  const options = payload === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
  const response = await fetcher(base + route, options);
  const result = await response.json();
  if (!response.ok) throw Object.assign(Error(result.message), {field: result.field});
  return result;
}
