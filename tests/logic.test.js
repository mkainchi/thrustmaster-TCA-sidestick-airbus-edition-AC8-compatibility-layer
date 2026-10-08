import { describe, it, expect } from 'vitest';
import { request, bindingLabel, capturedKey, modeLabel } from '../app/web/logic.js';

describe('keyboard and mode semantics', () => {
  it('labels modes and captures physical keys with modifiers', () => {
    expect(modeLabel('target-xbox')).toBe('TARGET → Xbox');
    expect(bindingLabel('Space')).toBe('Space');
    expect(bindingLabel({code:'KeyQ',modifiers:['shift']})).toBe('shift+KeyQ');
    const event = {code:'KeyQ', key:'q', ctrlKey:true, altKey:false, shiftKey:false,
      metaKey:false, isComposing:false, getModifierState:()=>false};
    expect(capturedKey(event)).toEqual({code:'KeyQ', modifiers:['ctrl']});
    expect(capturedKey({...event,code:'ShiftLeft',shiftKey:true})).toBeNull();
    expect(()=>capturedKey({...event,isComposing:true})).toThrow('standard');
  });
  it('does not silently accept a failed save', async () => {
    const fake = async()=>({ok:false,json:async()=>({message:'Choose a layout.'})});
    await expect(request(fake,'/session/','save',{})).rejects.toThrow('Choose a layout.');
  });
  it('preserves the field location supplied by server validation',async()=>{
    const fake=async()=>({ok:false,json:async()=>({message:'Choose a supported key.',field:'keys:roll_left'})});
    try { await request(fake,'/session/','save',{}); }
    catch(error) { expect(error.field).toBe('keys:roll_left');expect(error.message).toContain('supported key');return; }
    throw Error('Expected save validation to reject.');
  });
  it('uses GET for state and supports all standard modifier combinations', async()=>{
    const fake=async(url,options)=>({ok:true,json:async()=>({url,options})});
    expect(await request(fake,'/session/','state')).toEqual({url:'/session/state',options:{}});
    const e={code:'KeyA',key:'a',metaKey:false,isComposing:false,ctrlKey:false,altKey:false,shiftKey:false,getModifierState:()=>false};
    expect(capturedKey(e)).toEqual({code:'KeyA',modifiers:[]});
    expect(capturedKey({...e,altKey:true,shiftKey:true})).toEqual({code:'KeyA',modifiers:['alt','shift']});
    expect(capturedKey({...e,getModifierState:()=>true})).toEqual({code:'KeyA',modifiers:['altgr']});
    expect(()=>capturedKey({...e,metaKey:true})).toThrow('standard');
    expect(()=>capturedKey({...e,key:'Dead'})).toThrow('standard');
  });
});
