"""One-finger drawn shortcuts.

Hold a finger still for a moment -> "draw mode" -> draw a shape -> lift.
The shape is matched against templates ($1-recognizer style) and the matching
action runs. The cursor is put back where it was before the drawing started.
"""
import math
import os
import tempfile
import threading
import time

from . import actions

LOG_PATH = os.path.join(tempfile.gettempdir(), "thottu.log")


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except OSError:
        pass

HOLD_TIME = 0.35     # seconds still before draw mode arms
HOLD_SLOP = 0.015    # how far (pad fraction) the finger may wander while holding
MIN_STROKE = 0.08    # shortest stroke (pad fraction) we try to recognise
N_POINTS = 64
MATCH_THRESHOLD = 0.30


# ---------- templates ----------
def _poly(*pts, n=40):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for i in range(n):
            t = i / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(pts[-1])
    return out


def _arc(start_deg, end_deg, n=80):
    # screen coordinates (y down); angles measured like a clock face is not needed:
    # standard math angle, then flip y.
    return [(math.cos(math.radians(start_deg + (end_deg - start_deg) * i / n)),
             -math.sin(math.radians(start_deg + (end_deg - start_deg) * i / n))) for i in range(n + 1)]


TEMPLATES = [
    ("copy", _arc(50, 310)),                      # C: from upper-right, anticlockwise round to lower-right
    ("paste", _poly((0, 0), (0.5, 1), (1, 0))),   # V
    ("undo", _poly((0, 0), (1, 0), (0, 1), (1, 1))),  # Z
    ("enter", _poly((0, 0.55), (0.35, 1), (1, 0))),   # tick
    ("screenshot", _arc(90, 90 + 360)),           # circle anticlockwise from top
    ("screenshot", _arc(90, 90 - 360)),           # circle clockwise from top
]


def _resample(pts, n=N_POINTS):
    length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    if length == 0:
        return [pts[0]] * n
    step, acc, out = length / (n - 1), 0.0, [pts[0]]
    pts = list(pts)
    i = 1
    while i < len(pts):
        d = math.dist(pts[i - 1], pts[i])
        if acc + d >= step and d > 0:
            t = (step - acc) / d
            q = (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                 pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
            out.append(q)
            pts.insert(i, q)
            acc = 0.0
        else:
            acc += d
        i += 1
    while len(out) < n:
        out.append(pts[-1])
    return out[:n]


def _normalise(pts):
    pts = _resample(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    size = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    return [((x - cx) / size, (y - cy) / size) for x, y in pts]


_NORMALISED = [(name, _normalise(t)) for name, t in TEMPLATES]


def recognise(points):
    """Return (gesture name, score) — lower score is better — or (None, score)."""
    path = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    if path == 0 or math.dist(points[0], points[-1]) / path > 0.9:
        return None, 1.0  # a near-straight swipe is not a shortcut
    cand = _normalise(points)
    best, best_d = None, float("inf")
    for name, tmpl in _NORMALISED:
        d = sum(math.dist(a, b) for a, b in zip(cand, tmpl)) / N_POINTS
        if d < best_d:
            best, best_d = name, d
    return (best if best_d < MATCH_THRESHOLD else None), best_d


# ---------- live engine ----------
LABELS = {
    "copy": "Copied", "paste": "Pasted", "undo": "Undo",
    "enter": "Enter ✓", "screenshot": "Screenshot",
}


class GestureEngine:
    """Feed it touch frames; it runs actions. Overlay reads .state / .stroke / pop_label()."""

    def __init__(self):
        self.state = "idle"      # idle | hold | armed | drawing | cursor | multi
        self.stroke = []
        self.aspect = 1.6
        self._t0 = 0.0
        self._p0 = (0.0, 0.0)
        self._cursor0 = None
        self._label = None
        self._lock = threading.Lock()

    def pop_label(self):
        with self._lock:
            lbl, self._label = self._label, None
            return lbl

    def _say(self, text):
        with self._lock:
            self._label = text

    def feed(self, contacts, aspect):
        self.aspect = aspect
        down = [c for c in contacts if c["tip"]]
        now = time.time()

        if not down:
            if self.state == "drawing":
                self._finish()
            elif self.state in ("hold", "armed"):
                log(f"lifted while {self.state} after {now - self._t0:.2f}s (no drawing)")
            self.state, self.stroke = "idle", []
            return

        if len(down) > 1:
            if self.state in ("hold", "armed", "drawing"):
                actions.restore_cursor(self._cursor0)
            self.state, self.stroke = "multi", []
            return

        c = down[0]
        p = (c["x"] * aspect, c["y"])  # keep the real shape of the drawing
        if self.state == "idle":
            self.state, self._t0, self._p0 = "hold", now, p
            self._cursor0 = actions.get_cursor()
        elif self.state == "hold":
            if math.dist(p, self._p0) > HOLD_SLOP * aspect:
                self.state = "cursor"  # normal mouse use; ignore until lift
                log(f"moved after {now - self._t0:.2f}s -> normal mouse")
            elif now - self._t0 >= HOLD_TIME:
                self.state, self.stroke = "armed", [p]
                self._cursor0 = actions.get_cursor()
                log("armed: draw mode")
        elif self.state == "armed":
            self.stroke.append(p)
            if math.dist(p, self.stroke[0]) > HOLD_SLOP * aspect:
                self.state = "drawing"
        elif self.state == "drawing":
            self.stroke.append(p)

    def _finish(self):
        actions.restore_cursor(self._cursor0)
        pts = self.stroke
        span = max(max(x for x, _ in pts) - min(x for x, _ in pts),
                   max(y for _, y in pts) - min(y for _, y in pts)) if pts else 0
        if span < MIN_STROKE:
            log(f"stroke too small (span {span:.3f}, {len(pts)} pts)")
            return
        name, score = recognise(pts)
        best = min(((n, sum(math.dist(a, b) for a, b in zip(_normalise(pts), t)) / N_POINTS)
                    for n, t in _NORMALISED), key=lambda x: x[1])
        log(f"stroke span {span:.3f}, {len(pts)} pts -> {name} (closest {best[0]} {best[1]:.3f})")
        if name is None:
            self._say("?")
            return
        self._say(LABELS[name])
        threading.Thread(target=actions.run, args=(name,), daemon=True).start()
