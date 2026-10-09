"""Local keyboard profile editor. No hardware inventory, game saves or uploads."""
import ctypes
import sys

# Standard USB HID keyboard usages and PC Set-1 scan positions; these are
# protocol facts. No manufacturer header or keyboard translation table is copied.
LETTER_SCANS = [0x1e,0x30,0x2e,0x20,0x12,0x21,0x22,0x23,0x17,0x24,0x25,0x26,
                0x32,0x31,0x18,0x19,0x10,0x13,0x1f,0x14,0x16,0x2f,0x11,0x2d,0x15,0x2c]
CODE_HID = {f'Key{chr(65+i)}': 4+i for i in range(26)}
SCAN_HID = {scan: 4+i for i, scan in enumerate(LETTER_SCANS)}
for i, scan in enumerate(range(2, 12)):
    digit = str((i+1) % 10)
    CODE_HID['Digit'+digit] = 30+i
    SCAN_HID[scan] = 30+i
SPECIAL = {
    'Enter':(40,0x1c), 'Escape':(41,1), 'Backspace':(42,0x0e),
    'Tab':(43,0x0f), 'Space':(44,0x39), 'Minus':(45,0x0c),
    'Equal':(46,0x0d), 'BracketLeft':(47,0x1a), 'BracketRight':(48,0x1b),
    'Backslash':(49,0x2b), 'Semicolon':(51,0x27), 'Quote':(52,0x28),
    'Backquote':(53,0x29), 'Comma':(54,0x33), 'Period':(55,0x34),
    'Slash':(56,0x35), 'CapsLock':(57,0x3a), 'PrintScreen':(70,0xe037), 'ScrollLock':(71,0x46),
    'Pause':(72,0xe145), 'Insert':(73,0xe052), 'Home':(74,0xe047),
    'PageUp':(75,0xe049), 'Delete':(76,0xe053), 'End':(77,0xe04f),
    'PageDown':(78,0xe051), 'ArrowRight':(79,0xe04d), 'ArrowLeft':(80,0xe04b),
    'ArrowDown':(81,0xe050), 'ArrowUp':(82,0xe048), 'NumLock':(83,0x45),
    'NumpadDivide':(84,0xe035), 'NumpadMultiply':(85,0x37),
    'NumpadSubtract':(86,0x4a), 'NumpadAdd':(87,0x4e), 'NumpadEnter':(88,0xe01c),
    'Numpad1':(89,0x4f), 'Numpad2':(90,0x50), 'Numpad3':(91,0x51),
    'Numpad4':(92,0x4b), 'Numpad5':(93,0x4c), 'Numpad6':(94,0x4d),
    'Numpad7':(95,0x47), 'Numpad8':(96,0x48), 'Numpad9':(97,0x49),
    'Numpad0':(98,0x52), 'NumpadDecimal':(99,0x53), 'IntlBackslash':(100,0x56),
    'ContextMenu':(101,0xe05d), 'ControlLeft':(224,0x1d), 'ShiftLeft':(225,0x2a),
    'AltLeft':(226,0x38), 'MetaLeft':(227,0xe05b), 'ControlRight':(228,0xe01d),
    'ShiftRight':(229,0x36), 'AltRight':(230,0xe038), 'MetaRight':(231,0xe05c),
}
for name, (hid, scan) in SPECIAL.items():
    CODE_HID[name] = hid
    SCAN_HID[scan] = hid
for i in range(12):
    CODE_HID[f'F{i+1}'] = 58+i
    SCAN_HID[(0x3b+i if i < 10 else 0x57+i-10)] = 58+i
MOD_FLAGS = {'shift':0x10000, 'ctrl':0x100000, 'alt':0x40000, 'altgr':0x80000}
for i in range(12):
    CODE_HID[f'F{i+13}'] = 104+i
    SCAN_HID[0x64+i if i < 11 else 0x76] = 104+i


def physical_binding(binding):
    if set(binding) != {'code', 'modifiers'} or not isinstance(binding['code'], str) or binding['code'] not in CODE_HID:
        raise ValueError('Unsupported physical key. Use a standard key or a character binding.')
    modifiers = binding['modifiers']
    if not isinstance(modifiers, list) or any(not isinstance(m, str) or m not in MOD_FLAGS for m in modifiers):
        raise ValueError('Unsupported key modifier.')
    if len(modifiers) != len(set(modifiers)):
        raise ValueError('Invalid key modifiers.')
    return 1000+CODE_HID[binding['code']], modifiers


class WindowsLayouts:
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError('Keyboard layout detection requires Windows.')
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        self.api.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        self.api.GetKeyboardLayoutList.restype = ctypes.c_int
        self.api.GetKeyboardLayout.argtypes = [ctypes.c_uint32]
        self.api.GetKeyboardLayout.restype = ctypes.c_void_p
        self.api.GetForegroundWindow.restype = ctypes.c_void_p
        self.api.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.api.GetWindowThreadProcessId.restype = ctypes.c_uint32
        self.api.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
        self.api.VkKeyScanExW.restype = ctypes.c_short
        self.api.MapVirtualKeyExW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
        self.api.MapVirtualKeyExW.restype = ctypes.c_uint
        self.handles = {}
        count = self.api.GetKeyboardLayoutList(0, None)
        if count <= 0:
            raise RuntimeError('Windows did not return a keyboard layout. No layout was assumed.')
        handles = (ctypes.c_void_p * count)()
        count = self.api.GetKeyboardLayoutList(count, handles)
        for handle in handles[:count]:
            self.handles[f'{handle & 0xffffffff:08x}'] = handle
        thread = self.api.GetWindowThreadProcessId(self.api.GetForegroundWindow(), None)
        active = self.api.GetKeyboardLayout(thread)
        self.suggested = f'{active & 0xffffffff:08x}' if active else None
        self.items = [{'id':key, 'label':self.label(handle)} for key, handle in self.handles.items()]

    @staticmethod
    def label(handle):
        # Locale names and generic layout IDs only, never identity or hardware data.
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetLocaleInfoW.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_int]
        buf = ctypes.create_unicode_buffer(128)
        kernel.GetLocaleInfoW(handle & 0xffff, 0x72, buf, len(buf))
        return f'{buf.value or "Installed keyboard"} — Windows layout {handle & 0xffffffff:08x}'

    def resolve(self, binding, layout_id):
        if layout_id not in self.handles:
            raise ValueError('Select a currently installed Windows keyboard layout first.')
        if isinstance(binding, dict):
            return physical_binding(binding)
        if not isinstance(binding, str):
            raise ValueError('A binding must be a character, named key, or captured physical key.')
        if binding in CODE_HID and not binding.startswith(('Key', 'Digit')):
            return 1000+CODE_HID[binding], []
        if len(binding) != 1 or ord(binding) > 0xffff:
            raise ValueError('Use one character or a named key such as Space or ArrowUp.')
        handle = self.handles[layout_id]
        mapped = self.api.VkKeyScanExW(binding, handle)
        if mapped == -1:
            raise ValueError('A character is unavailable in the selected layout. Capture its physical key instead.')
        scan = self.api.MapVirtualKeyExW(mapped & 255, 4, handle)
        if scan not in SCAN_HID:
            raise ValueError('Unsupported scan code. Capture a standard physical key instead.')
        shift_state = (mapped >> 8) & 255
        if shift_state & ~7:
            raise ValueError('IME/special shift state unavailable. Capture a physical key instead.')
        modifiers = ['altgr'] if shift_state & 6 == 6 else [m for bit, m in ((2,'ctrl'),(4,'alt')) if shift_state & bit]
        if shift_state & 1:
            modifiers.append('shift')
        return 1000+SCAN_HID[scan], modifiers

