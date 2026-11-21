"""Keyboard shortcuts and cursor helpers, sent with plain Win32 calls."""
import ctypes
import time
from ctypes import wintypes as wt

user32 = ctypes.windll.user32
KEYUP = 0x0002

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


ACTIONS = {
    "copy": lambda: press("ctrl", "c"),
    "paste": lambda: press("ctrl", "v"),
    "undo": lambda: press("ctrl", "z"),
    "enter": lambda: press("enter"),
    "screenshot": lambda: press("win", "printscreen"),  # saved to Pictures\Screenshots
}


def run(name):
    time.sleep(0.05)  # let the finger-lift settle first
    ACTIONS[name]()
