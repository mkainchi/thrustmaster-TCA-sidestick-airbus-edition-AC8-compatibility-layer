export const labels = {keyboard: 'Keyboard', xbox: 'Xbox', 'target-xbox': 'TARGET → Xbox'};
export const modeLabel = mode => labels[mode];
export const bindingLabel = binding => typeof binding === 'string' ? binding : [...binding.modifiers, binding.code].join('+');

export function capturedKey(event) {
  if (event.metaKey || event.isComposing || event.key === 'Dead') {
    throw Error('Choose a standard game key; system shortcuts and text composition are unsupported.');
  }
  if (/^(Shift|Control|Alt)/.test(event.code)) return null;
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
