"""Nicknames for Glide Agent: what you write -> the exact WhatsApp name.

Only needed when they differ ("didi" -> "Didi Ltst"); any other name is searched as written.
Saved in %APPDATA%\\Glide\\contacts.json.
"""
import json
import os
import threading

PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Glide", "contacts.json")
DEFAULT = {"didi": "Didi Ltst"}

_lock = threading.Lock()
_contacts = None


def load():
    global _contacts
    with _lock:
        if _contacts is None:
            try:
                with open(PATH, encoding="utf-8") as f:
                    _contacts = json.load(f)
            except (OSError, ValueError):
                _contacts = dict(DEFAULT)
        return dict(_contacts)


def _save():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(_contacts, f, ensure_ascii=False, indent=1)


def add(nickname, whatsapp_name):
    load()
    with _lock:
        _contacts[nickname.strip().lower()] = whatsapp_name.strip()
        _save()


def remove(nickname):
    load()
    with _lock:
        _contacts.pop(nickname, None)
        _save()
