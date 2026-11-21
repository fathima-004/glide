"""Write mode: write with your finger, pick the language, it's typed at the cursor.

Enter: hold TWO fingers still for a moment.
Write: one finger, as many strokes as you like (lift between letters).
Read:  about 1 s after your last stroke, Gemma reads it; Sarvam converts it.
Pick:  the options appear at the cursor:
         Malayalam written -> മലയാളം · English
         English written   -> English
         Manglish written  -> English · മലയാളം
       Rest a finger on the matching part of the touchpad (left to right) until the
       ring fills. Do nothing for a few seconds to cancel.
"""
import threading
import time

from . import actions, handwriting, sarvam

IDLE_TO_READ = 1.1     # seconds after last stroke before reading
NOTHING_WRITTEN = 6.0  # leave write mode if nothing is written
WAIT_FOR_MESSAGE = 20.0  # after a name/address, this long to start writing the message
PENDING_SECONDS = 90.0   # a name stays chosen this long, even across write sessions
REMEMBER_NAME = False    # off: every new writing starts with a contact, so the person can change
FINISH_AFTER = 2.0       # WhatsApp/Gmail: stop writing this long and the words are used
CHOICE_TIMEOUT = 10.0
DWELL = 0.8           # seconds on a card to type it
SWIPE_TIME = 0.7      # a slant swipe is quick...
SWIPE_MIN = 0.2       # ...and covers at least this much of the pad both across and down
AUTO_SPEAK = False    # speak the Malayalam reading as soon as cards appear (parked for now)

# Parked while write mode is kept simple (built step by step with the user); the code stays.
VOICE_ENABLED = False     # read options aloud, voice-note card
SEND_ROW_ENABLED = False  # favourites / voice / do-it row, slant swipes
DIRECT_COMMANDS = False   # "w-name msg" / "mail ..." act straight away

MAL, ENG = "മലയാളം", "English"  # card labels: മലയാളം, English
ARA = "العربية"  # العربية

ARABIC_TO_ENGLISH = """Translate this Arabic text to natural English. Keep the meaning exactly,
add nothing. Text: "{text}"
Reply with ONLY JSON: {{"english": "<translation>"}}"""


def arabic_to_english(text):
    """Sarvam covers Indian languages only, so Arabic is translated by Gemma (Gemini backup)."""
    out = handwriting.ask_json(ARABIC_TO_ENGLISH.format(text=text)) or {}
    return out.get("english")


def _parallel(jobs):
    found = {}

    def run(name, fn):
        try:
            found[name] = (fn() or "").strip()
        except Exception as e:
            print("sarvam job failed:", e)

    threads = [threading.Thread(target=run, args=(n, f)) for n, f in jobs.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(9)
    return found


def build_choices(result):
    """Gemma's reading -> the language options, as (label, text).

    Arabic    -> العربية (as written) · English (Gemma translate; Sarvam has no Arabic)
    Malayalam -> മലയാളം (as written) · English (Sarvam translate)
    English   -> English (as written)
    Manglish  -> English (Sarvam: Manglish -> Malayalam -> English) · മലയാളം (Sarvam transliterate)
    Unclear   -> English (as written) · മലയാളം (transliterated)
    """
    text, lang = result["text"], result.get("language", "unknown")
    if lang == "arabic":
        found = _parallel({"en": lambda: arabic_to_english(text)})
        choices = [(ARA, text), (ENG, found.get("en"))]
    elif lang == "malayalam":
        found = _parallel({"en": lambda: sarvam.translate(text, "ml-IN", "en-IN")})
        choices = [(MAL, text), (ENG, found.get("en"))]
    elif lang == "english":
        choices = [(ENG, text)]
    elif lang == "manglish":
        def meaning():
            ml = sarvam.manglish_to_malayalam(text)
            return sarvam.translate(ml, "ml-IN", "en-IN") if ml else None
        found = _parallel({"en": meaning, "ml": lambda: sarvam.manglish_to_malayalam(text)})
        choices = [(ENG, found.get("en")), (MAL, found.get("ml"))]
    else:
        found = _parallel({"ml": lambda: sarvam.manglish_to_malayalam(text)})
        choices = [(ENG, text), (MAL, found.get("ml"))]
    out, seen = [], set()
    for label, t in choices:
        if t and t not in seen:
            seen.add(t)
            out.append((label, t))
    return out or [(ENG, text)]


def build_sends(choices, written):
    """Bottom row: one-touch 'send to' cards for favourite people, then voice note and Do it.

    Returns (cards, targets): cards are (label, text shown) and targets maps a card's position
    in the row to (kind, target). WhatsApp sends the Malayalam version when there is one;
    mail sends a proper English email made from what was written.
    """
    from . import contacts
    mal = next((t for _, t in choices if any("ഀ" <= ch <= "ൿ" for ch in t)), None)
    cards, targets = [], {}
    for label, kind, target in contacts.send_targets():
        targets[len(cards)] = (kind, target)
        cards.append((label, (mal or written) if kind == "whatsapp" else "English email"))
    cards.append((VOICE, mal or written))
    cards.append((DO_IT, written))  # Glide Agent: treat what was written as a goal
    return cards, targets


VOICE = "\U0001F3A4 Voice note"
DO_IT = "⚡ Do it"
SILENT = ("✉", DO_IT)  # cards that aren't read aloud


TIDY_PROMPT = """Turn this text into a short email. Text: "{text}"
Rules:
- Keep exactly the same meaning and facts. Only fix grammar and make it read as a proper sentence.
- Do NOT add anything that isn't in the text: no reasons, requests, offers, dates, names,
  apologies or extra sentences.
- Start the body with a greeting line and end with a closing line, in the same language as
  the text (English: "Hi," and "Thanks,"; Malayalam: "നമസ്കാരം," and "നന്ദി,";
  Arabic: "مرحباً،" and "شكراً،").
- Subject: a short, natural email subject (2-6 words, same language) that sums up the text.
  Reword it a little so it reads like a real subject line (e.g. "I will not come tomorrow"
  -> "Not coming tomorrow", "work is finished" -> "Work completed", "send the report" ->
  "Request for the report"), but add no new information and keep who does what: a request
  stays a request, something you did stays something you did.
Reply with ONLY JSON: {{"subject": "...", "body": "..."}}"""


def tidy_mail(text):
    """(subject, body): the text tidied into an email without adding any content.
    Falls back to the text as written if the AI isn't available."""
    words = text.split()
    subject = " ".join(words[:6]) + ("…" if len(words) > 6 else "")
    try:
        out = handwriting.ask_json(TIDY_PROMPT.format(text=text)) or {}
        if out.get("body"):
            return (out.get("subject") or subject).strip(), out["body"].strip()
    except Exception as e:
        print("tidy failed:", e)
    return subject, text


def _chrome_tab_in_front(word):
    """True when the window in front is Chrome showing a tab whose title contains word."""
    try:
        import ctypes
        from . import agent
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return word in buf.value.lower() and agent._exe_of(hwnd) == "chrome.exe"
    except Exception as e:
        print("window check failed:", e)
        return False


def in_whatsapp_web():
    """True when the window in front is WhatsApp Web in Chrome."""
    return _chrome_tab_in_front("whatsapp")


def in_gmail():
    """True when the window in front is Gmail in Chrome."""
    return _chrome_tab_in_front("gmail")


def is_direct_command(text):
    """Writing that is clearly an instruction skips the cards: 'w-name msg' or 'mail …'."""
    from .agent import QUICK
    t = text.strip().lower()
    return bool(QUICK.match(text)) or t.startswith(("mail ", "email ", "m-"))


class Writer:
    def __init__(self, say):
        self.say = say
        self.mode = None          # None | writing | reading | choosing
        self.strokes = []         # list of strokes, each list of (x, y) with x scaled by aspect
        self.choices = []
        self.highlight = None     # index being held in choosing mode
        self.anchor = None
        self._last_change = 0.0
        self._touching = False
        self._pick_t0, self._pick_p0 = 0.0, None
        self.progress, self.finger_x, self.picked, self._picked_t = 0.0, None, None, 0.0
        self.audio, self.choose_t0 = {}, 0.0
        self.agent_status = ""
        self.n_type = 0           # cards in the top row; the rest are the bottom (send) row
        self.targets = {}         # bottom-row position -> (kind, target) for favourite people
        self.written = ""
        self.finger_y = None
        self.in_whatsapp = False
        self.wa_contact = None    # in WhatsApp: the person named by the first word
        self.chat_open = False    # their chat has been opened already
        self.in_gmail = False
        self.mail_to = None       # in Gmail: the address made from the first word
        self._pending = None      # (kind, who, time): a name written whose message hasn't been sent
        self.word_jobs = []       # WhatsApp/Gmail: words read one by one while writing
        self.header = ""          # shown above the cards, e.g. "To: Rashid"
        self._swipe = None        # (x, y, time) where the current touch started, for slant swipes

    @property
    def active(self):
        return self.mode is not None

    def start(self, anchor):
        self.in_whatsapp = in_whatsapp_web()  # the voice-note option only makes sense there
        self.in_gmail = not self.in_whatsapp and in_gmail()
        self.wa_contact, self.header, self.chat_open, self.mail_to = None, "", False, None
        pending = self._pending if REMEMBER_NAME else None
        if pending and time.time() - pending[2] < PENDING_SECONDS:
            kind, who, _ = pending
            if kind == "whatsapp" and self.in_whatsapp:  # a name was written, the message wasn't yet
                self.wa_contact, self.header, self.chat_open = who, f"To: {who}", True
            elif kind == "mail" and self.in_gmail:
                self.mail_to, self.header = who, f"To: {who}"
        self.mode, self.strokes, self.choices, self.anchor = "writing", [], [], anchor
        self.word_jobs = []
        self._last_change, self._touching = time.time(), False
        self._await_release = True  # the two fingers that opened write mode are still down
        actions_log("write mode")

    def abort(self):
        """Esc: stop at once. A pending send is cancelled (nothing is sent)."""
        self._agent_touched = True  # makes any running countdown stop without sending
        self.word_jobs = []
        self.cancel("Cancelled")

    def cancel(self, msg=None):
        self.mode, self.strokes, self.choices, self.highlight = None, [], [], None
        if msg:
            self.say(msg)

    def feed(self, down, aspect, now):
        actions.restore_cursor(self.anchor)  # pointer stays put while writing/picking
        if self.mode == "writing":
            if self._await_release:
                if not down:
                    self._await_release = False
                    self._last_change = now
                return
            if down:
                c = down[0]
                p = (c["x"] * aspect, c["y"])
                if not self._touching:
                    self.strokes.append([p])
                    self._touching = True
                else:
                    self.strokes[-1].append(p)
            else:
                self._touching = False
            self._last_change = now
        elif self.mode == "choosing":
            self._feed_pick(down, now)
        elif self.mode == "agent":
            # a NEW touch (after lifting) cancels a pending send
            if not down:
                self._agent_lifted = True
            elif self._agent_lifted:
                self._agent_touched = True

    def row_of(self, idx):
        return 0 if idx < self.n_type else 1

    def _feed_pick(self, down, now):
        """Finger position picks a card live; staying on it fills a ring; full ring does it.

        The touchpad is split like the cards: top half = top row (what to type),
        bottom half = bottom row (send to / voice / do it); left-to-right = the cards.
        """
        if not down:
            if SEND_ROW_ENABLED and self._swipe and self.finger_x is not None:
                sx, sy, st = self._swipe
                dx, dy = self.finger_x - sx, self.finger_y - sy
                if now - st <= SWIPE_TIME and abs(dx) >= SWIPE_MIN and abs(dy) >= SWIPE_MIN:
                    # y grows downwards: "/" has dx and dy of opposite sign, "\" the same sign
                    self._swipe = None
                    self._slant("mail" if (dx > 0) != (dy > 0) else "whatsapp")
                    return
            self._swipe = None
            self.finger_x, self.finger_y, self.highlight, self.progress, self._pick_p0 = \
                None, None, None, 0.0, None
            return
        x, y = down[0]["x"], down[0]["y"]
        if self._swipe is None:
            self._swipe = (x, y, now)
        self.finger_x, self.finger_y, self._pick_p0 = x, y, x
        n_send = len(self.choices) - self.n_type
        bottom = n_send > 0 and (y >= 0.5 or self.n_type == 0)
        start, n = (self.n_type, n_send) if bottom else (0, self.n_type)
        idx = start + min(int(x * n), n - 1)
        if idx != self.highlight:
            self.highlight, self._pick_t0 = idx, now
            self._play(idx)
        self.progress = min((now - self._pick_t0) / DWELL, 1.0)
        if self.progress >= 1.0:
            label, text = self.choices[idx]
            self.mode, self.picked, self._picked_t = "picked", idx, now
            target = self.targets.get(idx - self.n_type) if bottom else None
            if target:
                kind, who = target
                self.mode, self.agent_status = "agent", f"⚡ {label}…"
                threading.Thread(target=self._run_send, args=(kind, who, text), daemon=True).start()
            elif self.wa_contact and label == VOICE:  # WhatsApp: voice note to the named person
                self.mode, self.agent_status = "agent", f"\U0001F3A4 Voice note for {self.wa_contact}…"
                threading.Thread(target=self._wa_voice, args=(self.wa_contact, text), daemon=True).start()
            elif self.mail_to:                        # Gmail: mail with this text as the content
                self.mode, self.agent_status = "agent", f"✉ To {self.mail_to}…"
                threading.Thread(target=self._mail_text, args=(self.mail_to, text), daemon=True).start()
            elif self.wa_contact:                     # WhatsApp: message to the named person
                self.mode, self.agent_status = "agent", f"⚡ To {self.wa_contact}…"
                threading.Thread(target=self._wa_text, args=(self.wa_contact, text), daemon=True).start()
            elif label == VOICE:
                threading.Thread(target=self._send_voice, args=(idx, text), daemon=True).start()
            elif label == DO_IT:
                self.mode, self.agent_status = "agent", "⚡ Thinking…"
                threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()
            else:
                threading.Thread(target=_type_later, args=(text,), daemon=True).start()

    def _slant(self, kind):
        """'/' = mail, '\\' = WhatsApp: send to the only such favourite, or show just those people."""
        from . import contacts
        field = "email" if kind == "mail" else "whatsapp"
        people = [(nick, p[field]) for nick, p in contacts.people().items() if p[field]]
        actions_log(f"slant -> {kind}: {people}")
        if not people:
            self.say("No " + ("email" if kind == "mail" else "WhatsApp") + " favourite — add one in Favourites")
            return
        mal = next((t for _, t in self.choices[:self.n_type] if any("ഀ" <= ch <= "ൿ" for ch in t)), None)
        text = (mal or self.written) if kind == "whatsapp" else "English email"
        if len(people) == 1:
            nick, target = people[0]
            self.mode, self.agent_status = "agent", f"⚡ {nick[:1].upper() + nick[1:]}…"
            threading.Thread(target=self._run_send, args=(kind, target, text), daemon=True).start()
            return
        icon = "✉" if kind == "mail" else "\U0001F4AC"
        sends = [(f"{icon} {nick[:1].upper() + nick[1:]}", text) for nick, _ in people[:5]]
        self.targets = {i: (kind, target) for i, (_, target) in enumerate(people[:5])}
        self.choices = self.choices[:self.n_type] + sends
        self.highlight, self._last_change = None, time.time()
        self.say("Pick who — bottom half")

    def _mail_text(self, to, text):
        """Gmail compose to `to` with the chosen text, tidied into an email (no new content)."""
        from . import agent
        self._agent_lifted, self._agent_touched = False, False
        self._agent_status("✉ Tidying the wording…")
        subject, body = tidy_mail(text)
        step = {"action": "gmail", "to": to, "to_name": "", "subject": subject, "body": body}
        try:
            result = agent._gmail(step, self._agent_status, lambda: self._agent_touched)
        except Exception as e:
            print("mail failed:", e)
            result = "Couldn't send the mail — try again"
        if str(result).startswith("\u2713"):
            self._pending = None  # sent: the next writing starts with a name again
        self.cancel(result)

    def _wa_text(self, contact, text):
        """Text message to the WhatsApp contact; their chat is normally open already."""
        from . import agent
        self._agent_lifted, self._agent_touched = False, False
        cancelled = lambda: self._agent_touched  # noqa: E731
        try:
            if self.chat_open:
                result = agent.send_text_here(contact, text, self._agent_status, cancelled)
            else:
                result = agent._whatsapp({"contact": contact, "message": text}, self._agent_status, cancelled)
        except Exception as e:
            print("send failed:", e)
            result = "Couldn't send — try again"
        if str(result).startswith("\u2713"):
            self._pending = None  # sent: the next writing starts with a name again
        self.cancel(result)

    def _wa_voice(self, contact, text):
        """Sarvam voice clip (OGG/Opus, WhatsApp's own format) sent to a WhatsApp contact."""
        import os
        import tempfile
        from . import agent
        self._agent_lifted, self._agent_touched = False, False
        safe = "".join(ch for ch in text if ch.isalnum() or ch in " _-" or "ഀ" <= ch <= "ൿ")
        folder = os.path.join(tempfile.gettempdir(), "glide_voice")
        os.makedirs(folder, exist_ok=True)
        self._agent_status("\U0001F3A4 Making the voice note (Sarvam)…")
        try:
            for codec in ("ogg", "mp3"):
                path = os.path.join(folder, f"Glide voice - {safe[:30].strip() or 'message'}.{codec}")
                if sarvam.speak_to_file(text, path, codec=codec):
                    break
            else:
                self.cancel("Voice failed — try again")
                return
            result = agent.send_voice_note(contact, path, self._agent_status, lambda: self._agent_touched,
                                           chat_open=self.chat_open)
        except Exception as e:
            print("voice note failed:", e)
            result = "Voice failed — try again"
        if str(result).startswith("\u2713"):
            self._pending = None  # sent: the next writing starts with a name again
        self.cancel(result)

    def _agent_status(self, text):
        self.agent_status = text
        actions_log("agent: " + text)

    def _run_agent(self, goal):
        from . import agent
        self._agent_lifted, self._agent_touched = False, False
        try:
            result = agent.run(goal, self._agent_status, cancelled=lambda: self._agent_touched)
        except Exception as e:
            print("agent failed:", e)
            result = "Agent failed — try again"
        self.cancel(result)

    def _run_send(self, kind, who, text):
        """One-touch send to a favourite: WhatsApp message or an English email."""
        from . import agent
        self._agent_lifted, self._agent_touched = False, False
        cancelled = lambda: self._agent_touched  # noqa: E731
        try:
            if kind == "whatsapp":
                result = agent._whatsapp({"contact": who, "message": text}, self._agent_status, cancelled)
            else:
                self._agent_status("⚡ Writing the email…")
                step = agent.quick_mail(f"mail {who} {self.written}")
                result = agent._gmail(step, self._agent_status, cancelled)
        except Exception as e:
            print("send failed:", e)
            result = "Couldn't send — try again"
        self.cancel(result)

    def _send_voice(self, idx, text):
        """Make a Sarvam voice clip and paste it as a file (WhatsApp shows it, ✓ sends).

        OGG/Opus is WhatsApp's own voice-note format, so it plays inline in the chat on
        phones and desktop; MP3 is the fallback. (WAV would arrive as a document.)
        """
        import os
        import subprocess
        import tempfile
        safe = "".join(ch for ch in text if ch.isalnum() or ch in " _-" or "ഀ" <= ch <= "ൿ")
        safe = safe[:30].strip() or "message"
        folder = os.path.join(tempfile.gettempdir(), "glide_voice")
        os.makedirs(folder, exist_ok=True)
        self.say("\U0001F3A4 Making voice note…")
        try:
            for codec in ("ogg", "mp3"):
                path = os.path.join(folder, f"Glide voice - {safe}.{codec}")
                if sarvam.speak_to_file(text, path, codec=codec):
                    break
            else:
                self.say("Voice failed")
                return
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Set-Clipboard -LiteralPath '{path}'"],
                           creationflags=0x08000000, timeout=10)
            time.sleep(0.15)
            actions.press("ctrl", "v")
            self.say("\U0001F3A4 Voice note ready — draw ✓ to send")
        except Exception as e:
            print("voice note failed:", e)
            self.say("Voice failed")

    def _play(self, idx):
        path = self.audio.get(idx)
        if path and VOICE_ENABLED:
            try:
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                print("audio failed:", e)

    def _prefetch_audio(self, choices):
        import os
        import tempfile
        is_mal = lambda t: any("ഀ" <= ch <= "ൿ" for ch in t)  # noqa: E731
        # Malayalam first, so it can be spoken automatically as soon as it's ready
        order = sorted(range(len(choices)), key=lambda i: not is_mal(choices[i][1]))
        done, spoken = {}, False
        for i in order:
            text = choices[i][1]
            if self.choices is not choices:
                return  # a new word was written meanwhile
            if choices[i][0].startswith(SILENT):
                continue
            try:
                if text in done:
                    self.audio[i] = done[text]
                    continue
                path = os.path.join(tempfile.gettempdir(), f"glide_choice_{i}.wav")
                if sarvam.speak_to_file(text, path):
                    done[text] = self.audio[i] = path
                    if self.highlight == i:
                        self._play(i)  # finger was already waiting on this card
                    elif AUTO_SPEAK and self.highlight is None and not spoken and is_mal(text):
                        self._play(i)  # auto-speak the Malayalam reading
                        spoken = True
            except Exception as e:
                print("tts failed:", e)

    def tick(self, now):
        """Called ~60x/s from the overlay; handles timeouts with no finger frames."""
        if self.mode == "writing":
            wait = WAIT_FOR_MESSAGE if (self.wa_contact or self.mail_to) else NOTHING_WRITTEN
            if not self.strokes and not self.word_jobs and now - self._last_change > wait:
                self.cancel("Write mode off")
            elif self.word_by_word and self.strokes and not self._touching \
                    and now - self._last_change > IDLE_TO_READ:
                job = {"done": False, "text": None, "language": None}  # one word, read in the background
                self.word_jobs.append(job)
                threading.Thread(target=self._read_word, args=(job, list(self.strokes)), daemon=True).start()
                self.strokes, self._last_change = [], now
            elif self.word_by_word and not self.strokes and self.word_jobs and not self._touching \
                    and now - self._last_change > FINISH_AFTER and all(j["done"] for j in self.word_jobs):
                self.mode = "reading"
                threading.Thread(target=self._finish_words, daemon=True).start()
            elif not self.word_by_word and self.strokes and not self._touching \
                    and now - self._last_change > IDLE_TO_READ:
                self.mode = "reading"
                threading.Thread(target=self._read, args=(list(self.strokes),), daemon=True).start()
        elif self.mode == "choosing" and now - self._last_change > CHOICE_TIMEOUT \
                and self._pick_p0 is None:
            self.cancel("Cancelled")
        elif self.mode == "picked" and now - self._picked_t > 0.85:
            self.cancel()

    def _read(self, strokes):
        from .keys import get_key
        if not get_key("GEMINI_API_KEY"):
            self.cancel("Gemini key not set")
            return
        try:
            result = handwriting.recognise(handwriting.strokes_to_png(strokes))
        except Exception as e:
            print("handwriting failed:", e)
            result = None
        if not result:
            self.cancel("Couldn't read that — try bigger")
            return
        self._handle(result)

    @property
    def word_by_word(self):
        """In WhatsApp/Gmail you write several words on the same small pad: read them one by one."""
        return self.in_whatsapp or self.in_gmail

    @property
    def words_so_far(self):
        return [j["text"] or "\u2026" for j in self.word_jobs]

    def _read_word(self, job, strokes):
        try:
            res = handwriting.recognise(handwriting.strokes_to_png(strokes))
        except Exception as e:
            print("handwriting failed:", e)
            res = None
        if res:
            job["text"], job["language"] = res["text"], res.get("language")
        job["done"] = True

    def _finish_words(self):
        """All words read: first = contact / address (unless already chosen), the rest = message."""
        words = [j for j in self.word_jobs if j["text"]]
        self.word_jobs = []
        if not words:
            self.cancel("Couldn't read that \u2014 try bigger")
            return
        text = " ".join(j["text"] for j in words)
        msg_langs = [j["language"] for j in (words if (self.wa_contact or self.mail_to) else words[1:])]
        if any("\u0600" <= ch <= "\u06ff" for ch in text):
            lang = "arabic"
        elif "manglish" in msg_langs:
            lang = "manglish"
        elif msg_langs and all(l == "english" for l in msg_langs):
            lang = "english"
        else:
            lang = "unknown"
        self._handle({"text": text, "script": "latin", "language": lang, "alternatives": []})

    def _handle(self, result):
        """Turn a reading into options (and, in WhatsApp/Gmail, a contact/address + message)."""
        if DIRECT_COMMANDS and is_direct_command(result["text"]):  # "w-didi ..", "mail ..": do it
            actions_log(f"direct command: {result['text']}")
            self.mode, self.agent_status = "agent", "⚡ " + result["text"]
            self._run_agent(result["text"])
            return
        if self.in_whatsapp and not self.wa_contact:
            # in WhatsApp: the first word names the person (any WhatsApp contact). Open their chat
            # right away; the rest (written now or after a pause) is the message.
            from . import agent, contacts
            words = result["text"].split()
            nick = words[0].strip(",.:-")
            self.wa_contact = contacts.load().get(nick.lower()) or nick[:1].upper() + nick[1:]
            self.header = f"To: {self.wa_contact}"
            self.mode = "agent"
            err = agent.open_chat(self.wa_contact, self._agent_status)
            if err:
                self.cancel(err)
                return
            self.chat_open = True
            self._pending = ("whatsapp", self.wa_contact, time.time())
            if len(words) < 2:  # only the name so far: now write the message
                self.mode, self.strokes, self._touching = "writing", [], False
                self._await_release, self._last_change = False, time.time()
                return
            result = dict(result, text=" ".join(words[1:]))
            if result.get("language") == "malayalam" and not any(
                    "ഀ" <= ch <= "ൿ" for ch in result["text"]):
                result["language"] = "unknown"
        if self.in_gmail and not self.mail_to:
            # in Gmail: the first word is the address (word -> word@gmail.com), the rest is the mail
            from . import contacts
            words = result["text"].split()
            who = words[0].strip(",.:-")
            self.mail_to = who if "@" in who else (contacts.email_of(who) or who.lower() + "@gmail.com")
            self.header = f"To: {self.mail_to}"
            self._pending = ("mail", self.mail_to, time.time())
            if len(words) < 2:  # only the address so far: now write the mail
                self.mode, self.strokes, self._touching = "writing", [], False
                self._await_release, self._last_change = False, time.time()
                return
            result = dict(result, text=" ".join(words[1:]))
            if result.get("language") == "malayalam" and not any(
                    "ഀ" <= ch <= "ൿ" for ch in result["text"]):
                result["language"] = "unknown"
        typed = build_choices(result)
        if self.in_whatsapp:
            # in WhatsApp Web: offer a Sarvam voice note (Malayalam if there is a Malayalam option)
            mal = next((t for label, t in typed if label == MAL), None)
            typed = typed + [(VOICE, mal or result["text"])]
        sends, targets = build_sends(typed, result["text"]) if SEND_ROW_ENABLED else ([], {})
        choices = typed + sends
        actions_log(f"read {result} -> {choices}")
        self.audio, self.highlight, self.progress, self.finger_x = {}, None, 0.0, None
        self.n_type, self.targets, self.written = len(typed), targets, result["text"]
        self.choices = choices
        self.mode, self._last_change, self._pick_p0 = "choosing", time.time(), None
        self.choose_t0 = time.time()
        if VOICE_ENABLED:
            threading.Thread(target=self._prefetch_audio, args=(choices,), daemon=True).start()


_CHIME = None


def _chime():
    """Short soft two-note chime (generated once, played async)."""
    global _CHIME
    try:
        import math
        import os
        import struct
        import tempfile
        import wave
        import winsound
        if _CHIME is None:
            _CHIME = os.path.join(tempfile.gettempdir(), "glide_chime.wav")
            rate = 22050
            frames = bytearray()
            for freq, dur in ((880, 0.09), (1320, 0.16)):
                n = int(rate * dur)
                for i in range(n):
                    env = min(i / 200, 1) * (1 - i / n)
                    frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * freq * i / rate)))
            with wave.open(_CHIME, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(bytes(frames))
        winsound.PlaySound(_CHIME, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as e:
        print("chime failed:", e)


def _type_later(text):
    time.sleep(0.1)
    actions.type_text(text)


def actions_log(msg):
    from .gestures import log
    log(msg)
