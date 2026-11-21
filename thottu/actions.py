"""Keyboard shortcuts, mouse and cursor helpers, sent with plain Win32 calls."""
import ctypes
import subprocess
import threading
import time
from ctypes import wintypes as wt

user32 = ctypes.windll.user32
KEYUP = 0x0002
MOUSE_LEFTDOWN, MOUSE_LEFTUP = 0x0002, 0x0004

VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "enter": 0x0D,
      "tab": 0x09, "printscreen": 0x2C, "c": 0x43, "v": 0x56, "z": 0x5A, "s": 0x53}


def press(*keys):
    """Press a chord like press('ctrl', 'c')."""
    codes = [VK[k] for k in keys]
    for k in codes:
        user32.keybd_event(k, 0, 0, 0)
    time.sleep(0.02)
    for k in reversed(codes):
        user32.keybd_event(k, 0, KEYUP, 0)


def get_cursor():
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def restore_cursor(pos):
    if pos:
        user32.SetCursorPos(*pos)


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def mouse_down():
    user32.mouse_event(MOUSE_LEFTDOWN, 0, 0, 0, 0)


def mouse_up():
    user32.mouse_event(MOUSE_LEFTUP, 0, 0, 0, 0)


def move_by(dx, dy):
    """Move the cursor by whole pixels, clamped to the screen."""
    x, y = get_cursor()
    w, h = screen_size()
    user32.SetCursorPos(min(max(int(round(x + dx)), 0), w - 1),
                        min(max(int(round(y + dy)), 0), h - 1))


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def type_text(text):
    """Type any Unicode text (Malayalam too) at the cursor."""
    KEYEVENTF_UNICODE = 0x0004
    data = text.encode("utf-16-le")
    units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
    seq = []
    for u in units:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYUP):
            inp = _INPUT(type=1)
            inp.ki = _KEYBDINPUT(0, u, flags, 0, 0)
            seq.append(inp)
    arr = (_INPUT * len(seq))(*seq)
    user32.SendInput(len(seq), arr, ctypes.sizeof(_INPUT))


def right_click():
    user32.mouse_event(0x0008, 0, 0, 0, 0)
    user32.mouse_event(0x0010, 0, 0, 0, 0)


def tap_vk(code, times=1):
    for _ in range(times):
        user32.keybd_event(code, 0, 0, 0)
        user32.keybd_event(code, 0, KEYUP, 0)


# --- brightness: WMI is slow, so set a target and apply it once the finger settles ---
_bright = {"level": None, "target": None, "timer": None}
_bright_lock = threading.Lock()
_NO_WINDOW = 0x08000000


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                          text=True, creationflags=_NO_WINDOW, timeout=10).stdout.strip()


def _apply_brightness():
    with _bright_lock:
        target = _bright["target"]
    _ps("(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods)"
        f" | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={target}}}")


def brightness_step(delta):
    with _bright_lock:
        if _bright["level"] is None:
            try:
                _bright["level"] = int(_ps("(Get-CimInstance -Namespace root/wmi "
                                           "-ClassName WmiMonitorBrightness).CurrentBrightness"))
            except (ValueError, subprocess.SubprocessError):
                _bright["level"] = 50
        _bright["level"] = min(max(_bright["level"] + delta, 0), 100)
        _bright["target"] = _bright["level"]
        if _bright["timer"]:
            _bright["timer"].cancel()
        _bright["timer"] = threading.Timer(0.15, _apply_brightness)
        _bright["timer"].start()
    return _bright["level"]


ACTIONS = {
    "copy": lambda: press("ctrl", "c"),
    "paste": lambda: press("ctrl", "v"),
    "undo": lambda: press("ctrl", "z"),
    "enter": lambda: press("enter"),
    "screenshot": lambda: press("win", "printscreen"),  # saved to Pictures\Screenshots
    "task_view": lambda: press("win", "tab"),
    "switch_app": lambda: press("alt", "tab"),
    "desktop": lambda: press("win", "d"),
    "right_click": right_click,
    "volume_up": lambda: tap_vk(0xAF, 2),
    "volume_down": lambda: tap_vk(0xAE, 2),
    "brightness_up": lambda: brightness_step(+6),
    "brightness_down": lambda: brightness_step(-6),
    "next_tab": lambda: press("ctrl", "tab"),
    "prev_tab": lambda: press("ctrl", "shift", "tab"),
}


def run(name):
    time.sleep(0.05)  # let the finger-lift settle first
    ACTIONS[name]()


def run_now(name):
    ACTIONS[name]()
