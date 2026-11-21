"""Write mode: write a word with your finger, pick how it gets typed.

Enter: hold TWO fingers still for a moment.
Write: one finger, as many strokes as you like (lift between letters).
Read:  about 1 s after your last stroke, Gemini reads it; Sarvam converts it.
Pick:  up to 3 choices appear at the cursor, left to right. Hold one finger still
       on the left / middle / right of the touchpad, then lift, to type that choice.
       Do nothing for a few seconds to cancel.
"""
import threading
import time

from . import actions, handwriting, sarvam

IDLE_TO_READ = 1.1     # seconds after last stroke before reading
NOTHING_WRITTEN = 6.0  # leave write mode if nothing is written
CHOICE_TIMEOUT = 10.0
DWELL = 0.8           # seconds on a card to type it
AUTO_SPEAK = False    # speak the Malayalam reading as soon as cards appear (parked for now)


def build_choices(result):
    """Gemini result -> list of (label, text) choices, de-duplicated."""
    text, script = result["text"], result.get("script", "latin")
    jobs = {}
    if script == "malayalam":
        jobs["English"] = lambda: sarvam.translate(text, "ml-IN", "en-IN")
    else:
        jobs["\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02"] = lambda: sarvam.manglish_to_malayalam(text)
        jobs["Translation"] = lambda: sarvam.translate(text, "en-IN", "ml-IN")
    found = {}

    def run(name, fn):
        try:
            found[name] = fn()
        except Exception as e:
            print("sarvam job failed:", e)

    threads = [threading.Thread(target=run, args=(n, f)) for n, f in jobs.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join(9)

    choices = [("As written", text)]
    for name in jobs:
        if found.get(name):
            choices.append((name, found[name].strip()))
    for alt in result.get("alternatives", []):
        choices.append(("Or", alt))
    seen, out = set(), []
    for label, t in choices:
        if t and t not in seen:
            seen.add(t)
            out.append((label, t))
    out = out[:3]
    # voice-note card: speak the Malayalam version if we have one, else the text as written
    mal = next((t for _, t in out if any("ഀ" <= ch <= "ൿ" for ch in t)), None)
    out.append((VOICE, mal or text))
    return out


VOICE = "\U0001F3A4 Voice note"


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

    @property
    def active(self):
        return self.mode is not None

    def start(self, anchor):
        self.mode, self.strokes, self.choices, self.anchor = "writing", [], [], anchor
        self._last_change, self._touching = time.time(), False
        self._await_release = True  # the two fingers that opened write mode are still down
        actions_log("write mode")

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

    def _feed_pick(self, down, now):
        """Finger position picks a card live; staying on it fills a ring; full ring types it."""
        if not down:
            self.finger_x, self.highlight, self.progress, self._pick_p0 = None, None, 0.0, None
            return
        x = down[0]["x"]
        self.finger_x, self._pick_p0 = x, x
        n = len(self.choices)
        idx = min(int(x * n), n - 1)
        if idx != self.highlight:
            self.highlight, self._pick_t0 = idx, now
            self._play(idx)
        self.progress = min((now - self._pick_t0) / DWELL, 1.0)
        if self.progress >= 1.0:
            label, text = self.choices[idx]
            self.mode, self.picked, self._picked_t = "picked", idx, now
            if label == VOICE:
                threading.Thread(target=self._send_voice, args=(idx, text), daemon=True).start()
            else:
                threading.Thread(target=_type_later, args=(text,), daemon=True).start()

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
        if path:
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
            if not self.strokes and now - self._last_change > NOTHING_WRITTEN:
                self.cancel("Write mode off")
            elif self.strokes and not self._touching and now - self._last_change > IDLE_TO_READ:
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
        choices = build_choices(result)
        actions_log(f"read {result} -> {choices}")
        self.audio, self.highlight, self.progress, self.finger_x = {}, None, 0.0, None
        self.choices = choices
        self.mode, self._last_change, self._pick_p0 = "choosing", time.time(), None
        self.choose_t0 = time.time()
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
