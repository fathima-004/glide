"""Favourite people for Glide: a nickname with a WhatsApp name and/or an email.

They appear as one-touch "send to" cards after you write a message, so you never have to
write a name. Typed commands ("w-didi ...", "mail didi ...") use the same nicknames.
Saved in %APPDATA%\\Glide\\contacts.json as {"didi": {"whatsapp": "Didi Ltst", "email": ""}}.
"""
import json
import os
import threading

PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Glide", "contacts.json")
DEFAULT = {"didi": {"whatsapp": "Didi Ltst", "email": ""},
           "rashid": {"whatsapp": "", "email": "rashrahn@gmail.com"}}

_lock = threading.Lock()
_people = None


def _norm(entry):
    if isinstance(entry, str):  # older format: nickname -> WhatsApp name
        return {"whatsapp": entry, "email": ""}
    return {"whatsapp": entry.get("whatsapp", ""), "email": entry.get("email", "")}


def people():
    """{nickname: {"whatsapp": ..., "email": ...}} in the order they were added."""
    global _people
    with _lock:
        if _people is None:
            try:
                with open(PATH, encoding="utf-8") as f:
                    _people = {k: _norm(v) for k, v in json.load(f).items()}
            except (OSError, ValueError):
                _people = {k: dict(v) for k, v in DEFAULT.items()}
        return {k: dict(v) for k, v in _people.items()}


def load():
    """nickname -> WhatsApp name (for the agent planner)."""
    return {k: v["whatsapp"] for k, v in people().items() if v["whatsapp"]}


def email_of(nickname):
    return people().get(nickname.lower(), {}).get("email", "")


def _save():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(_people, f, ensure_ascii=False, indent=1)


def add(nickname, whatsapp_name="", email=""):
    people()
    with _lock:
        _people[nickname.strip().lower()] = {"whatsapp": whatsapp_name.strip(), "email": email.strip()}
        _save()


def remove(nickname):
    people()
    with _lock:
        _people.pop(nickname, None)
        _save()


def send_targets(limit=3):
    """The first few favourites as send cards: (label, kind, target)."""
    out = []
    for nick, p in people().items():
        name = nick[:1].upper() + nick[1:]
        if p["whatsapp"]:
            out.append((f"\U0001F4AC {name}", "whatsapp", p["whatsapp"]))
        elif p["email"]:
            out.append((f"✉ {name}", "mail", p["email"]))
        if len(out) >= limit:
            break
    return out
