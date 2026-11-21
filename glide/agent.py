"""Glide Agent: write a goal with one finger, and Glide does the multi-step task.

    "didi varam"       -> WhatsApp: open Didi's chat, type "ഞാൻ വരാം", wait for ✓ to send
    "boat race video"  -> YouTube search for Nehru Trophy boat race
    "mail sir leave"   -> Gmail draft of a polite leave letter

The plan comes from Gemma (Gemini as the safety net); Malayalam messages are written
with Sarvam. Messages are never sent by themselves: Glide stops and you draw ✓ to send.
"""
import ctypes
import os
import time
import urllib.parse
import webbrowser
from ctypes import wintypes as wt

from . import actions, handwriting, sarvam

user32 = ctypes.windll.user32


def contacts():
    """Nicknames from the Contacts window (tray menu), saved in %APPDATA%\\Glide\\contacts.json."""
    from . import contacts as store
    return store.load()


PLAN_PROMPT = """You are the planner inside Glide, a laptop tool for people using one hand.
The user wrote a short goal with their finger, often in Manglish (Malayalam in English letters)
or short English. Turn it into ONE action. Reply with ONLY JSON.

Known WhatsApp contacts (nickname -> exact WhatsApp name): {contacts}
If the person is not in that list, use the name as written, capitalised (e.g. "amma" -> "Amma",
"rahul" -> "Rahul"); WhatsApp search will find it.

Actions:
- {{"action": "whatsapp", "contact": "<exact WhatsApp name>", "message_en": "<the message in natural English>", "language": "ml" or "en"}}
  Use "ml" (Malayalam) when the goal is Manglish or the contact is family; otherwise "en".
- {{"action": "youtube", "query": "<search words>"}}
- {{"action": "gmail", "to": "<email or empty>", "subject": "<subject>", "body": "<short polite email body>"}}
- {{"action": "search", "query": "<web search words>"}}
- {{"action": "maps", "query": "<place>"}}
- {{"action": "none", "reason": "<why>"}}

Also include "say": a 3-6 word description of what you'll do, e.g. "Message Didi: I'll come".

Examples:
"didi varam" -> {{"action":"whatsapp","contact":"Didi Ltst","message_en":"I will come","language":"ml","say":"Message Didi: I'll come"}}
"boat race video" -> {{"action":"youtube","query":"Nehru Trophy boat race","say":"Boat race videos on YouTube"}}
"mail sir leave" -> {{"action":"gmail","to":"","subject":"Leave request","body":"Dear Sir,\\n\\nI would like to request leave for today as I am unwell.\\n\\nThank you,","say":"Draft leave mail to sir"}}

Goal: "{goal}"
"""


def plan(goal):
    c = contacts()
    p = handwriting.ask_json(PLAN_PROMPT.format(goal=goal, contacts=", ".join(f"{k} -> {v}" for k, v in c.items())))
    return p or {"action": "none", "reason": "couldn't plan"}


# ---------- doing it ----------
def _focus_window(title_part):
    """Bring the first visible window whose title contains title_part to the front."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_part.lower() in buf.value.lower():
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    actions.press("alt")        # lets this process take the foreground
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return True


def _whatsapp(step, status):
    contact = step.get("contact") or ""
    msg = step.get("message_en") or ""
    if step.get("language") == "ml" and msg:
        status(f"⚡ Writing it in Malayalam (Sarvam)…")
        msg = sarvam.translate(msg, "en-IN", "ml-IN") or msg
    status("⚡ Opening WhatsApp…")
    if not _focus_window("WhatsApp"):
        webbrowser.open("https://web.whatsapp.com")
        time.sleep(8)
        if not _focus_window("WhatsApp"):
            return "Open WhatsApp Web first"
    status(f"⚡ Finding {contact}…")
    actions.press("esc")
    time.sleep(0.2)
    actions.press("ctrl", "alt", "slash")  # WhatsApp Web: search chats
    time.sleep(0.6)
    actions.press("ctrl", "a")
    actions.type_text(contact)
    time.sleep(1.2)
    actions.press("enter")                 # open the top match
    time.sleep(1.0)
    status(f"⚡ Typing to {contact}…")
    actions.type_text(msg)
    return f"Ready: “{msg}” — draw ✓ to send"


def _open(url, status, what):
    status(f"⚡ {what}…")
    webbrowser.open(url)
    return what


def run(goal, status):
    """Plan and carry out the goal. status(text) shows progress. Returns a final message."""
    status("⚡ Thinking…")
    step = plan(goal)
    a = step.get("action")
    if step.get("say"):
        status("⚡ " + step["say"])
        time.sleep(0.6)
    q = urllib.parse.quote_plus
    if a == "whatsapp":
        return _whatsapp(step, status)
    if a == "youtube":
        return _open("https://www.youtube.com/results?search_query=" + q(step.get("query", "")), status,
                     "YouTube: " + step.get("query", ""))
    if a == "gmail":
        url = ("https://mail.google.com/mail/?view=cm&fs=1&to=" + q(step.get("to", "")) + "&su=" +
               q(step.get("subject", "")) + "&body=" + q(step.get("body", "")))
        return _open(url, status, "Gmail draft ready")
    if a == "search":
        return _open("https://www.google.com/search?q=" + q(step.get("query", "")), status,
                     "Searching: " + step.get("query", ""))
    if a == "maps":
        return _open("https://www.google.com/maps/search/" + q(step.get("query", "")), status,
                     "Maps: " + step.get("query", ""))
    return "Couldn't do that: " + step.get("reason", "try again")
