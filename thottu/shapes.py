"""Your own shapes: draw any shape 3 times, attach an action, and Thottu learns your hand.

Saved in %APPDATA%\\Thottu\\shapes.json as
    [{"label": "WhatsApp", "action": {"type": "open", "value": "whatsapp:"}, "samples": [[[x, y], ...], ...]}]
"""
import json
import os
import threading
import webbrowser

from . import actions

PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Thottu", "shapes.json")
SAMPLES_NEEDED = 3

# What a shape can do. "value" is filled from the dialog for the "…" ones.
PRESETS = [
    ("WhatsApp", {"type": "open", "value": "whatsapp:", "fallback": "https://web.whatsapp.com"}),
    ("Gmail", {"type": "open", "value": "https://mail.google.com"}),
    ("YouTube", {"type": "open", "value": "https://www.youtube.com"}),
    ("Google Meet", {"type": "open", "value": "https://meet.google.com"}),
    ("Lock laptop", {"type": "lock"}),
    ("Calculator", {"type": "open", "value": "calc"}),
    ("Website…", {"type": "open", "value": ""}),
    ("Type my text…", {"type": "type", "value": ""}),
]

_lock = threading.Lock()
_shapes = None


def load():
    global _shapes
    with _lock:
        if _shapes is None:
            try:
                with open(PATH, encoding="utf-8") as f:
                    _shapes = json.load(f)
            except (OSError, ValueError):
                _shapes = []
        return _shapes


def save():
    with _lock:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_shapes or [], f, ensure_ascii=False)


def add(label, action, samples):
    shapes = load()
    with _lock:
        shapes[:] = [s for s in shapes if s["label"] != label]  # re-teaching replaces
        shapes.append({"label": label, "action": action, "samples": samples})
    save()


def remove_all():
    load()
    with _lock:
        _shapes.clear()
    save()


def run(shape):
    """Do what a learned shape is attached to."""
    a = shape["action"]
    kind, value = a.get("type"), a.get("value", "")
    try:
        if kind == "open":
            try:
                os.startfile(value)
            except OSError:
                if a.get("fallback"):
                    webbrowser.open(a["fallback"])
                else:
                    raise
        elif kind == "lock":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif kind == "type":
            actions.type_text(value)
    except Exception as e:
        print("shape action failed:", e)
