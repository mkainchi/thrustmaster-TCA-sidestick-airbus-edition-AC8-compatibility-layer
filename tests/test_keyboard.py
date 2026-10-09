from types import SimpleNamespace
import pytest
from app import keyboard as k
from tests.test_windows import Fn


def api_factory(active=0x040c, count=3, label='Installed language'):
    def handles(size, pointer):
        if size:
            for i,value in enumerate((0x0409,0x040c,0x0407)):pointer[i]=value
        return count
    def name(locale,flag,buffer,length):buffer.value=label;return len(label)
    return SimpleNamespace(GetKeyboardLayoutList=Fn(handles),GetKeyboardLayout=Fn(lambda thread:active),
        GetForegroundWindow=Fn(lambda:1),GetWindowThreadProcessId=Fn(lambda *a:2),GetLocaleInfoW=Fn(name),
        VkKeyScanExW=Fn(lambda char, handle: ord(char.upper())),MapVirtualKeyExW=Fn(lambda vk, mode, handle:k.LETTER_SCANS[vk-65]))


def layouts(api=None):
    value=object.__new__(k.WindowsLayouts);value.api=api or api_factory();value.handles={'00000409':0x0409,'0000040c':0x040c,'00000407':0x0407}
    return value


def test_readonly_layout_enumeration_and_locale_fallback(monkeypatch):
    fake=api_factory()
    monkeypatch.setattr(k.ctypes,'WinDLL',lambda *a,**kw:fake)
    obj=k.WindowsLayouts()
    assert obj.suggested=='0000040c' and len(obj.items)==3
    fake.GetKeyboardLayout=Fn(lambda thread:0)
    fake.GetLocaleInfoW=api_factory(label='').GetLocaleInfoW
    obj=k.WindowsLayouts();assert obj.suggested is None and 'Installed keyboard' in obj.items[0]['label']
    fake.GetKeyboardLayoutList=Fn(lambda *a:0)
    with pytest.raises(RuntimeError,match='No layout'):k.WindowsLayouts()
    monkeypatch.setattr(k.sys,'platform','other')
    with pytest.raises(RuntimeError,match='Windows'):k.WindowsLayouts()


def test_us_french_and_german_resolve_different_positions():
    fake=api_factory()
    def scan(vk,mode,handle):
        char=chr(vk)
        if handle==0x040c:char={'A':'Q','Q':'A','W':'Z'}.get(char,char)
        if handle==0x0407:char={'Y':'Z','Z':'Y'}.get(char,char)
        return k.LETTER_SCANS[ord(char)-65]
    fake.MapVirtualKeyExW=Fn(scan); obj=layouts(fake)
    assert obj.resolve('a','00000409')==(1004,[])
    assert obj.resolve('a','0000040c')==(1020,[])
    assert obj.resolve('y','00000407')==(1029,[])
    assert obj.resolve('Space','00000409')==(1044,[])
    assert obj.resolve({'code':'KeyA','modifiers':['ctrl']},'00000407')==(1004,['ctrl'])


@pytest.mark.parametrize('binding',[None, 'KeyA','Digit1','long','😀',{}, {'code':'BAD','modifiers':[]},
 {'code':'KeyA','modifiers':'shift'},{'code':'KeyA','modifiers':['bad']},
 {'code':'KeyA','modifiers':['ctrl','ctrl']}, {'code':[],'modifiers':[]}, {'code':'KeyA','modifiers':[{}]}])
def test_invalid_bindings_fail_without_fallback(binding):
    with pytest.raises(ValueError):layouts().resolve(binding,'00000409')


def test_invalid_layout_untranslatable_character_and_scan():
    obj=layouts()
    with pytest.raises(ValueError):obj.resolve('a','not-installed')
    obj.api.VkKeyScanExW=Fn(lambda *a:-1)
    with pytest.raises(ValueError,match='unavailable'):obj.resolve('☃','00000409')
    obj.api.VkKeyScanExW=Fn(lambda *a:ord('A'))
    obj.api.MapVirtualKeyExW=Fn(lambda *a:999)
    with pytest.raises(ValueError,match='scan'):obj.resolve('a','00000409')
    obj.api.MapVirtualKeyExW=Fn(lambda *a:0x1e)
    for bits, expected in ((0,[]),(1,['shift']),(2,['ctrl']),(4,['alt']),(6,['altgr']),(7,['altgr','shift'])):
        obj.api.VkKeyScanExW=Fn(lambda *a,bits=bits:ord('A')|(bits<<8))
        assert obj.resolve('a','00000409')==(1004,expected)
    obj.api.VkKeyScanExW=Fn(lambda *a:ord('A')|(8<<8))
    with pytest.raises(ValueError,match='IME'):obj.resolve('a','00000409')
@pytest.mark.parametrize('code,hid', [('PrintScreen', 70), ('F13', 104), ('F24', 115), ('ControlLeft', 224), ('AltRight', 230)])
def test_extended_standard_physical_keys(code, hid):
    from app.keyboard import physical_binding
    assert physical_binding({'code': code, 'modifiers': []}) == (1000+hid, [])
