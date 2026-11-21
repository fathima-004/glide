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
PICK_HOLD = 0.3
PICK_SLOP = 0.03


def build_choices(result):
    """Gemini result -> list of (label, text) choices, de-duplicated."""
    text, script = result["text"], result.get("script", "latin")
    jobs = {}
    if script == "malayalam":
        jobs["English"] = lambda: sarvam.translate(text, "ml-IN", "en-IN")
    else:
        jobs["Malayalam"] = lambda: sarvam.manglish_to_malayalam(text)
        jobs["Translated"] = lambda: sarvam.translate(text, "en-IN", "ml-IN")
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
    return out[:3]


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
        if down:
            c = down[0]
            p = (c["x"], c["y"])
            if self._pick_p0 is None:
                self._pick_t0, self._pick_p0 = now, p
            elif abs(p[0] - self._pick_p0[0]) + abs(p[1] - self._pick_p0[1]) > PICK_SLOP * 3:
                self._pick_t0, self._pick_p0 = now, p  # moved: restart the hold
            n = len(self.choices)
            idx = min(int(p[0] * n), n - 1)
            self.highlight = idx if now - self._pick_t0 >= PICK_HOLD else None
        else:
            if self.highlight is not None:
                label, text = self.choices[self.highlight]
                self.cancel("Typed: " + text)
                threading.Thread(target=_type_later, args=(text,), daemon=True).start()
            self._pick_p0 = None

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
        self.choices = build_choices(result)
        actions_log(f"read {result} -> {self.choices}")
        self.mode, self._last_change, self._pick_p0 = "choosing", time.time(), None


def _type_later(text):
    time.sleep(0.1)
    actions.type_text(text)


def actions_log(msg):
    from .gestures import log
    log(msg)
