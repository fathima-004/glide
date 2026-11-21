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


# ---------- Chrome ----------
kernel32 = ctypes.windll.kernel32


def chrome_path():
    """chrome.exe from App Paths (per-user or machine), else the usual install folders."""
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as k:
                path = winreg.QueryValue(k, None)
                if path and os.path.exists(path):
                    return path
        except OSError:
            pass
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", "")):
        path = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
        if os.path.exists(path):
            return path
    return None


def open_in_chrome(url):
    path = chrome_path()
    if path:
        import subprocess
        subprocess.Popen([path, url])
    else:
        webbrowser.open(url)  # no Chrome installed: default browser


def _exe_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    size = wt.DWORD(520)
    kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(h)
    return os.path.basename(buf.value).lower()


def _chrome_windows():
    """Visible Chrome windows as (hwnd, title)."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if _exe_of(hwnd) == "chrome.exe":
                    found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return found


def _focus(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    actions.press("alt")            # lets this process take the foreground
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)


def _foreground_title():
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def focus_whatsapp_in_chrome(status):
    """WhatsApp Web, always in Chrome: reuse its window/tab; open it only if it isn't there."""
    wins = _chrome_windows()
    for hwnd, title in wins:                 # 1. a Chrome window already showing WhatsApp
        if "whatsapp" in title.lower():
            _focus(hwnd)
            return True
    if wins:                                 # 2. WhatsApp may be a background tab: Chrome tab search
        _focus(wins[0][0])
        actions.press("ctrl", "shift", "a")
        time.sleep(0.6)
        actions.type_text("WhatsApp")
        time.sleep(0.6)
        actions.press("enter")
        time.sleep(0.8)
        if "whatsapp" in _foreground_title().lower():
            return True
        actions.press("esc")
    status("⚡ Opening WhatsApp Web in Chrome…")  # 3. not open anywhere: open it in Chrome
    open_in_chrome("https://web.whatsapp.com")
    for _ in range(20):
        time.sleep(0.5)
        for hwnd, title in _chrome_windows():
            if "whatsapp" in title.lower():
                time.sleep(4)                # let the chat list load
                _focus(hwnd)
                return True
    return False


def _whatsapp(step, status):
    contact = step.get("contact") or ""
    msg = step.get("message_en") or ""
    if step.get("language") == "ml" and msg:
        status(f"⚡ Writing it in Malayalam (Sarvam)…")
        msg = sarvam.translate(msg, "en-IN", "ml-IN") or msg
    status("⚡ Opening WhatsApp in Chrome…")
    if not focus_whatsapp_in_chrome(status):
        return "Couldn't open WhatsApp Web in Chrome"
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
    open_in_chrome(url)
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
