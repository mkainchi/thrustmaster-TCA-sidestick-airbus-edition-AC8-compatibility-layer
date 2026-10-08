"""Native Windows joystick input and licensed ViGEmClient output."""
import ctypes as c
import math
from contextlib import contextmanager


@contextmanager
def controller_guard(api=None):
    """One controller owner across all extracted copies in this Windows session."""
    api = api if api is not None else load_dll('kernel32.dll')
    api.CreateMutexW.argtypes = [c.c_void_p, c.c_int, c.c_wchar_p]
    api.CreateMutexW.restype = c.c_void_p
    api.WaitForSingleObject.argtypes = [c.c_void_p, c.c_uint32]
    api.ReleaseMutex.argtypes = [c.c_void_p]
    api.CloseHandle.argtypes = [c.c_void_p]
    handle = api.CreateMutexW(None, False, 'Local\\tca-airbus-config-controller-owner-v1')
    if not handle:
        raise RuntimeError('Windows could not reserve the controller session. Close other emulation windows and retry.')
    owned = False
    try:
        if api.WaitForSingleObject(handle, 0) not in (0, 128):
            raise RuntimeError('Another TCA configuration package is emulating. Stop its session first.')
        owned = True
        yield
    finally:
        if owned:
            api.ReleaseMutex(handle)
        api.CloseHandle(handle)


class Caps(c.Structure):
    _fields_ = [('mid', c.c_ushort), ('pid', c.c_ushort), ('name', c.c_wchar * 32)] + [
        (n, c.c_uint32) for n in ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax', 'buttons',
                                 'periodmin', 'periodmax', 'rmin', 'rmax', 'umin', 'umax', 'vmin', 'vmax',
                                 'caps', 'maxaxes', 'axes', 'maxbuttons')] + [
        ('regkey', c.c_wchar * 32), ('oem', c.c_wchar * 260)]


class JoyInfo(c.Structure):
    _fields_ = [(n, c.c_uint32) for n in ('size', 'flags', 'x', 'y', 'z', 'r', 'u', 'v',
                                        'buttons', 'button_number', 'pov', 'reserved1', 'reserved2')]


def load_dll(name):
    return c.WinDLL(str(name))


class DeviceInfo(c.Structure):
    _fields_ = [('size', c.c_uint32), ('guid', c.c_ubyte * 16), ('instance', c.c_uint32), ('reserved', c.c_size_t)]


def physical_present(api=None):
    """Check generic hardware IDs only; never read serials or device instance paths."""
    api = api if api is not None else load_dll('setupapi.dll')
    api.SetupDiGetClassDevsW.argtypes = [c.c_void_p, c.c_wchar_p, c.c_void_p, c.c_uint32]
    api.SetupDiGetClassDevsW.restype = c.c_void_p
    api.SetupDiEnumDeviceInfo.argtypes = [c.c_void_p, c.c_uint32, c.POINTER(DeviceInfo)]
    api.SetupDiGetDeviceRegistryPropertyW.argtypes = [c.c_void_p, c.POINTER(DeviceInfo), c.c_uint32,
                                                    c.c_void_p, c.c_void_p, c.c_uint32, c.c_void_p]
    api.SetupDiDestroyDeviceInfoList.argtypes = [c.c_void_p]
    handle = api.SetupDiGetClassDevsW(None, None, None, 6)
    if handle == c.c_void_p(-1).value:
        raise RuntimeError('Windows device presence could not be checked. Recheck controller drivers.')
    found = set()
    try:
        index = 0
        info = DeviceInfo(); info.size = c.sizeof(info)
        while api.SetupDiEnumDeviceInfo(handle, index, c.byref(info)):
            buffer = (c.c_ubyte * 4096)()
            if api.SetupDiGetDeviceRegistryPropertyW(handle, c.byref(info), 1, None, buffer, 4096, None):
                identifier = bytes(buffer).decode('utf-16-le').upper()
                for pid in ('0405', '0406', '0407'):
                    if 'VID_044F&PID_' + pid in identifier:
                        found.add(pid)
            index += 1
        return '0407' in found and bool(found & {'0405', '0406'})
    finally:
        api.SetupDiDestroyDeviceInfoList(handle)


class Joysticks:
    def __init__(self, api=None):
        self.api = api if api is not None else load_dll('winmm.dll')
        self.api.joyGetDevCapsW.argtypes = [c.c_size_t, c.POINTER(Caps), c.c_uint]
        self.api.joyGetPosEx.argtypes = [c.c_uint, c.POINTER(JoyInfo)]

    def refresh(self):
        self.api.joyConfigChanged.argtypes = [c.c_uint32]
        self.api.joyConfigChanged(0)

    def devices(self):
        devices = []
        for index in range(self.api.joyGetNumDevs()):
            caps = Caps()
            if self.api.joyGetDevCapsW(index, c.byref(caps), c.sizeof(caps)) == 0:
                info = JoyInfo(c.sizeof(JoyInfo), 255)
                if self.api.joyGetPosEx(index, c.byref(info)) == 0:
                    devices.append((index, caps))
        return devices

    def read(self, index, caps):
        info = JoyInfo(c.sizeof(JoyInfo), 255)
        if self.api.joyGetPosEx(index, c.byref(info)):
            raise RuntimeError('A controller disconnected. Reconnect it and restart emulation.')
        axes = []
        for name in 'xyzruv':
            low, high = getattr(caps, name + 'min'), getattr(caps, name + 'max')
            axes.append(0.0 if high <= low else max(-1, min(1, 2 * (getattr(info, name) - low) / (high - low) - 1)))
        hat = [0, 0]
        if info.pov != 65535:
            angle = math.radians(info.pov / 100)
            hat = [round(math.sin(angle)), round(math.cos(angle))]
        return {'axes': axes, 'buttons': [i + 1 for i in range(min(caps.buttons, 32)) if info.buttons & (1 << i)], 'hat': hat}

    def snapshot(self, mode):
        devices = self.devices()
        if mode == 'target-xbox':
            matches = [(i, cap) for i, cap in devices if cap.axes == 4 and cap.buttons == 32
                       and ('Combined' in cap.name or (cap.mid == 0x044f and cap.pid == 0xb10a))]
            if len(matches) != 1:
                raise RuntimeError('Waiting for TARGET Combined (4 axes, 32 buttons). Stop other TARGET profiles and retry.')
            data = self.read(*matches[0])
            return {'stick': {**data, 'buttons': [n for n in data['buttons'] if n <= 16]},
                    'quadrant': {**data, 'buttons': [n - 16 for n in data['buttons'] if n > 16], 'hat': [0, 0]}}
        result = {}
        for role, pids in (('stick', (0x0405, 0x0406)), ('quadrant', (0x0407,))):
            matches = [(i, cap) for i, cap in devices if cap.mid == 0x044f and cap.pid in pids]
            if len(matches) != 1:
                raise RuntimeError('Connect exactly one supported TCA sidestick and Quadrant Eng 1&2; stop TARGET for physical input.')
            result[role] = self.read(*matches[0])
        return result


class XReport(c.Structure):
    _fields_ = [('buttons', c.c_ushort), ('lt', c.c_ubyte), ('rt', c.c_ubyte)] + [
        (n, c.c_short) for n in ('lx', 'ly', 'rx', 'ry')]


class XState(c.Structure):
    _fields_ = [('packet', c.c_uint32), ('report', XReport)]


def xinput(api=None):
    api = api if api is not None else load_dll('xinput1_4.dll')
    api.XInputGetState.argtypes = [c.c_uint32, c.POINTER(XState)]
    states = {}
    for index in range(4):
        state = XState()
        if api.XInputGetState(index, c.byref(state)) == 0:
            states[index] = state.report
    return states


class Pad:
    def __init__(self, path, api=None):
        self.api = api if api is not None else c.CDLL(str(path))
        signatures = {
            'vigem_alloc': ([], c.c_void_p), 'vigem_free': ([c.c_void_p], None),
            'vigem_connect': ([c.c_void_p], c.c_uint), 'vigem_disconnect': ([c.c_void_p], None),
            'vigem_target_x360_alloc': ([], c.c_void_p), 'vigem_target_free': ([c.c_void_p], None),
            'vigem_target_add': ([c.c_void_p, c.c_void_p], c.c_uint),
            'vigem_target_remove': ([c.c_void_p, c.c_void_p], c.c_uint),
            'vigem_target_x360_update': ([c.c_void_p, c.c_void_p, XReport], c.c_uint)}
        for name, (args, result) in signatures.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = result
        self.bus = self.api.vigem_alloc()
        self.target = None
        self.attached = False
        if not self.bus:
            raise RuntimeError('Could not allocate the ViGEmBus client.')

    @staticmethod
    def check(code):
        if code != 0x20000000:
            raise RuntimeError('ViGEmBus is unavailable or unhealthy. Install/recheck the driver and restart Windows if required.')

    def connect(self, create=True):
        self.check(self.api.vigem_connect(self.bus))
        if create:
            self.target = self.api.vigem_target_x360_alloc()
            if not self.target:
                raise RuntimeError('Could not allocate the virtual Xbox controller.')
            self.check(self.api.vigem_target_add(self.bus, self.target))
            self.attached = True

    def update(self, values):
        data = XReport(int(values['buttons']), round(values['lt'] * 255), round(values['rt'] * 255),
                       *(round(values[n] * 32767) for n in ('lx', 'ly', 'rx', 'ry')))
        self.check(self.api.vigem_target_x360_update(self.bus, self.target, data))

    def close(self):
        try:
            if self.attached:
                try:
                    self.api.vigem_target_x360_update(self.bus, self.target, XReport())
                finally:
                    self.api.vigem_target_remove(self.bus, self.target)
        finally:
            if self.target:
                self.api.vigem_target_free(self.target)
                self.target = None
            if self.bus:
                self.api.vigem_disconnect(self.bus)
                self.api.vigem_free(self.bus)
                self.bus = None
            self.attached = False
