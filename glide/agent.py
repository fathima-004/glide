"""Glide Agent: write a goal with one finger, and Glide does the multi-step task.

    "w-didi varam"            -> WhatsApp Didi "varam" and send (quick syntax, no AI step)
    "didi varam"              -> WhatsApp Didi "ഞാൻ വരും" (AI plan + Sarvam Malayalam) and send
    "mail rashid work done"   -> Gmail to Rashid: subject + polite body, and send
    "boat race video"         -> YouTube search

The plan comes from Gemma (Gemini as the safety net); Malayalam messages are written with
Sarvam. Before anything is sent there is a 3-second countdown: touch the touchpad to cancel.
"""
import ctypes
import os
import re
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
- {{"action": "gmail", "to": "<email address if written, else empty>", "to_name": "<person's name, capitalised, e.g. Rashid>", "subject": "<subject>", "body": "<short polite email body, greeting the person by name>"}}
- {{"action": "search", "query": "<web search words>"}}
- {{"action": "maps", "query": "<place>"}}
- {{"action": "none", "reason": "<why>"}}

"mail <name> <what>", "email <name> <what>" and "m-<name> <what>" always mean the gmail action.

Also include "say": a 3-6 word description of what you'll do, e.g. "Message Didi: I'll come".

Examples:
"didi varam" -> {{"action":"whatsapp","contact":"Didi Ltst","message_en":"I will come","language":"ml","say":"Message Didi: I'll come"}}
"boat race video" -> {{"action":"youtube","query":"Nehru Trophy boat race","say":"Boat race videos on YouTube"}}
"mail rashid work completed" -> {{"action":"gmail","to":"","to_name":"Rashid","subject":"Work completed","body":"Hi Rashid,\\n\\nJust letting you know that the work is completed.\\n\\nThanks,","say":"Mail Rashid: work completed"}}

Goal: "{goal}"
"""


QUICK = re.compile(r"^\s*(w|wa|whatsapp)\s*[-:.–—]\s*(\S+)\s+(.+)$", re.I | re.S)


def quick_whatsapp(goal):
    """'w-didi varam' -> straight to WhatsApp, message exactly as written. None if not that form."""
    m = QUICK.match(goal)
    if not m:
        return None
    nick, msg = m.group(2).strip(), m.group(3).strip()
    name = contacts().get(nick.lower()) or nick[:1].upper() + nick[1:]
    return {"action": "whatsapp", "contact": name, "message": msg, "say": f"WhatsApp {name}: {msg}"}


MAIL = re.compile(r"^\s*(mail|email|e-mail|m)\s*[-:.–—]?\s*(\S+)\s+(.+)$", re.I | re.S)

MAIL_PROMPT = """Write a short, polite email from these few words: "{what}".
The words may be English, Malayalam script, or Manglish (Malayalam typed in English letters,
e.g. "pani kazhinju" = "the work is finished").
Literal meaning from Sarvam's Malayalam translator: "{meaning}". Trust this for the meaning of
Malayalam words (who will / won't do what, when), but fix obvious slips such as numbers or times
using the original words. Keep the email faithful: don't add requests or facts that aren't there.
Reply with ONLY JSON, writing subject and body in ENGLISH:
{{"subject": "<3-6 word subject>", "body": "<2-3 sentence email body, no greeting name, end with Thanks,>",
  "language": "ml" if the words were Malayalam script or Manglish, else "en"}}"""


def manglish_meaning(text, is_mal_script=False):
    """Sarvam: Manglish -> Malayalam script -> English, for the literal meaning."""
    try:
        ml = text if is_mal_script else sarvam.manglish_to_malayalam(text)
        return sarvam.translate(ml, "ml-IN", "en-IN") if ml else None
    except Exception as e:
        print("meaning failed:", e)
        return None


def quick_mail(goal):
    """'mail rashrahn work done' -> to rashrahn@gmail.com. The recipient is taken exactly from
    what was written (a word becomes <word>@gmail.com); only subject/body come from the AI."""
    m = MAIL.match(goal)
    if not m:
        return None
    who, what = m.group(2).strip().strip(",.:"), m.group(3).strip()
    from . import contacts as store
    to = who if "@" in who else (store.email_of(who) or who.lower() + "@gmail.com")
    is_mal_script = any("ഀ" <= ch <= "ൿ" for ch in what)
    meaning = manglish_meaning(what, is_mal_script) or what
    written = handwriting.ask_json(MAIL_PROMPT.format(what=what, meaning=meaning)) or {}
    subject = written.get("subject") or what[:1].upper() + what[1:]
    body = written.get("body") or what[:1].upper() + what[1:] + ".\n\nThanks,"
    greeting = "Hi,"
    # Manglish -> English email (what most inboxes expect); only Malayalam *script* stays Malayalam
    if is_mal_script:
        # Malayalam in -> Malayalam out, written by Sarvam
        if written.get("subject"):
            subject = sarvam.translate(subject, "en-IN", "ml-IN") or subject
            body = sarvam.translate(body, "en-IN", "ml-IN") or body
        elif is_mal_script:
            subject, body = what, what  # AI down: send the Malayalam exactly as written
        greeting = "നമസ്കാരം,"  # നമസ്കാരം,
    return {"action": "gmail", "to": to, "to_name": "", "subject": subject,
            "body": f"{greeting}\n\n{body}", "say": f"Mail {to}: {subject}"}


def plan(goal):
    quick = quick_whatsapp(goal) or quick_mail(goal)
    if quick:
        return quick
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


COUNTDOWN = 3  # seconds to cancel (by touching the touchpad) before anything is sent


def _countdown(what, status, cancelled):
    """Show 'Sending … in 3, 2, 1'. Returns False if the user touched the pad to cancel."""
    for left in range(COUNTDOWN, 0, -1):
        status(f"⚡ {what} in {left}…  (touch to cancel)")
        end = time.time() + 1
        while time.time() < end:
            if cancelled():
                return False
            time.sleep(0.05)
    return True


def _whatsapp(step, status, cancelled):
    contact = step.get("contact") or ""
    msg = step.get("message") or step.get("message_en") or ""
    if step.get("language") == "ml" and msg and "message" not in step:
        status("⚡ Writing it in Malayalam (Sarvam)…")
        msg = sarvam.translate(msg, "en-IN", "ml-IN") or msg
    err = open_chat(contact, status)
    if err:
        return err
    status(f"⚡ Typing to {contact}…")
    actions.type_text(msg)
    if not _countdown(f"Sending to {contact}", status, cancelled):
        return "Not sent — the message is waiting in the chat"
    actions.press("enter")
    return f"✓ Sent to {contact}: “{msg}”"


def open_chat(contact, status):
    """WhatsApp Web in Chrome -> search any contact by name -> open their chat. None if OK."""
    status("⚡ Opening WhatsApp in Chrome…")
    if not focus_whatsapp_in_chrome(status):
        return "Couldn't open WhatsApp Web in Chrome"
    status(f"⚡ Finding {contact}…")
    actions.press("esc")
    time.sleep(0.2)
    actions.press("ctrl", "alt", "slash")  # WhatsApp Web: search chats and contacts
    time.sleep(0.6)
    actions.press("ctrl", "a")
    actions.type_text(contact)
    time.sleep(1.5)                        # let WhatsApp list the matches
    actions.press("enter")                 # open the top match
    time.sleep(1.0)
    return None


def send_voice_note(contact, path, status, cancelled):
    """Open the contact's chat, paste the voice-note file, and send it after the countdown."""
    import subprocess
    err = open_chat(contact, status)
    if err:
        return err
    status(f"⚡ Attaching voice note for {contact}…")
    subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -LiteralPath '{path}'"],
                   creationflags=0x08000000, timeout=10)
    time.sleep(0.2)
    actions.press("ctrl", "v")
    time.sleep(1.8)                        # WhatsApp shows the attachment preview
    if not _countdown(f"Sending voice note to {contact}", status, cancelled):
        return "Not sent — the voice note is waiting in the chat"
    actions.press("enter")
    return f"✓ Voice note sent to {contact}"


def _wait_for_chrome_title(word, seconds=12):
    for _ in range(int(seconds / 0.5)):
        for hwnd, title in _chrome_windows():
            if word.lower() in title.lower():
                return hwnd
        time.sleep(0.5)
    return None


def _gmail(step, status, cancelled):
    q = urllib.parse.quote
    to = step.get("to", "") if "@" in step.get("to", "") else ""
    name = step.get("to_name") or ""
    url = ("https://mail.google.com/mail/?view=cm&fs=1&to=" + q(to) + "&su=" + q(step.get("subject", "")) +
           "&body=" + q(step.get("body", "")))
    status("⚡ Opening your Gmail in Chrome…")
    open_in_chrome(url)
    hwnd = _wait_for_chrome_title("Gmail")
    if not hwnd:
        return "Gmail didn't open — are you signed in in Chrome?"
    time.sleep(3.5)                     # let the compose window finish loading
    _focus(hwnd)
    if not to:
        if not name:
            return "Gmail draft ready — add who it's to"
        status(f"⚡ Finding {name} in your contacts…")
        actions.type_text(name)         # the To box has focus in a fresh compose window
        time.sleep(1.8)                 # Gmail shows matching contacts
        actions.press("enter")          # pick the top match
        time.sleep(0.5)
    who = to or name
    if not _countdown(f"Sending mail to {who}", status, cancelled):
        return "Not sent — the mail is waiting as a draft"
    actions.press("ctrl", "enter")      # Gmail: send
    return f"✓ Mail sent to {who}: {step.get('subject', '')}"


def _open(url, status, what):
    status(f"⚡ {what}…")
    open_in_chrome(url)
    return what


def run(goal, status, cancelled=lambda: False):
    """Plan and carry out the goal. status(text) shows progress; cancelled() is True if the
    user touched the pad during a countdown. Returns a final message."""
    status("⚡ Thinking…")
    step = plan(goal)
    a = step.get("action")
    if step.get("say"):
        status("⚡ " + step["say"])
        time.sleep(0.6)
    q = urllib.parse.quote_plus
    if a == "whatsapp":
        return _whatsapp(step, status, cancelled)
    if a == "youtube":
        return _open("https://www.youtube.com/results?search_query=" + q(step.get("query", "")), status,
                     "YouTube: " + step.get("query", ""))
    if a == "gmail":
        return _gmail(step, status, cancelled)
    if a == "search":
        return _open("https://www.google.com/search?q=" + q(step.get("query", "")), status,
                     "Searching: " + step.get("query", ""))
    if a == "maps":
        return _open("https://www.google.com/maps/search/" + q(step.get("query", "")), status,
                     "Maps: " + step.get("query", ""))
    return "Couldn't do that: " + step.get("reason", "try again")
