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
WRITE_HOLD = 0.5     # two fingers still this long -> write mode
DRAG_GAIN = 1.4     # full pad width moves the cursor 1.4 screen widths


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
    "task_view": "All windows", "switch_app": "Switch app",
    "desktop": "Desktop", "right_click": "Right-click",
    "volume_up": "\U0001F50A Volume +", "volume_down": "\U0001F509 Volume −",
    "brightness_up": "☀ Brighter", "brightness_down": "☀ Dimmer",
    "next_tab": "Next tab →", "prev_tab": "← Previous tab",
}

# Hold a finger still in a corner, then lift (no click, so nothing gets tapped by accident).
CORNERS = {"tl": "task_view", "tr": "switch_app", "bl": "desktop", "br": "right_click"}
CORNER_X, CORNER_Y = 0.15, 0.22
EDGE_X, EDGE_Y = 0.07, 0.10
SLIDE_STEP = 0.035   # pad height per volume/brightness step
TAB_STEP = 0.14      # pad width per tab
SLIDER_TEXT = {"left": "\U0001F50A Volume", "right": "☀ Brightness", "top": "Tabs"}


def zone(x, y):
    """Return (corner, edge) for a raw pad position; at most one is set."""
    h = "l" if x < CORNER_X else "r" if x > 1 - CORNER_X else None
    v = "t" if y < CORNER_Y else "b" if y > 1 - CORNER_Y else None
    if h and v:
        return v + h, None
    if x < EDGE_X:
        return None, "left"
    if x > 1 - EDGE_X:
        return None, "right"
    if y < EDGE_Y:
        return None, "top"
    return None, None


class GestureEngine:
    """Feed it touch frames; it runs actions. Overlay reads .state / .stroke / pop_label()."""

    def __init__(self):
        self.state = "idle"      # idle | hold | armed | drawing | cursor | multi | drag | slider
        self.stroke = []
        self.corner = None       # which corner the touch started in, if any
        self.edge = None         # which edge the touch started on, if any
        self.slider_text = ""
        self._r0 = (0.0, 0.0)
        self._slide_acc, self._slide_last = 0.0, (0.0, 0.0)
        self.aspect = 1.6
        self._t0 = 0.0
        self._p0 = (0.0, 0.0)
        self._cursor0 = None
        self.anchor = None       # screen point where the drawing is shown
        self._drag_last = {}     # contact id -> (x, y) during three-finger drag
        self._drag_rem = [0.0, 0.0]
        self._label = None
        self._lock = threading.Lock()
        self._two_t0, self._two_p0, self._two_moved = 0.0, (0.0, 0.0), True
        from .writer import Writer
        self.writer = Writer(self._say)

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

        if self.writer.active:
            self.writer.feed(down, aspect, now)
            self.state = "writer"
            return
        if self.state == "writer":  # write mode just ended: ignore until fingers lift
            if not down:
                self.state = "idle"
            return

        if not down:
            if self.state == "drawing":
                self._finish()
            elif self.state == "armed" and self.corner:
                actions.restore_cursor(self._cursor0)
                name = CORNERS[self.corner]
                log(f"corner {self.corner} -> {name}")
                self._say(LABELS[name])
                threading.Thread(target=actions.run, args=(name,), daemon=True).start()
            elif self.state == "slider":
                log(f"slider {self.edge} end")
            elif self.state in ("hold", "armed"):
                log(f"lifted while {self.state} after {now - self._t0:.2f}s (no drawing)")
            elif self.state == "drag":
                actions.mouse_up()
                log("drag end")
            self.state, self.stroke = "idle", []
            return

        if self.state == "drag" or len(down) >= 3:
            self._drag(down)
            return

        if len(down) > 1:
            if self.state in ("hold", "armed", "drawing"):
                actions.restore_cursor(self._cursor0)
            centre = (sum(c["x"] for c in down) / len(down), sum(c["y"] for c in down) / len(down))
            if self.state != "multi":
                if self.state not in ("hold", "armed", "drawing"):
                    self._cursor0 = actions.get_cursor()
                self.state, self.stroke = "multi", []
                self._two_t0, self._two_p0, self._two_moved = now, centre, False
            elif not self._two_moved:
                if math.dist(centre, self._two_p0) > HOLD_SLOP:
                    self._two_moved = True  # scrolling, not write mode
                elif now - self._two_t0 >= WRITE_HOLD:
                    self.anchor = self._cursor0
                    self.writer.start(self._cursor0)
                    self.state = "writer"
                    log("two-finger hold -> write mode")
            return

        c = down[0]
        p = (c["x"] * aspect, c["y"])  # keep the real shape of the drawing
        r = (c["x"], c["y"])  # raw pad position 0..1, for zones
        if self.state == "idle":
            self.state, self._t0, self._p0, self._r0 = "hold", now, p, r
            self._cursor0 = actions.get_cursor()
            self.corner, self.edge = zone(*r)
        elif self.state == "hold":
            if math.dist(p, self._p0) > HOLD_SLOP * aspect:
                dx, dy = r[0] - self._r0[0], r[1] - self._r0[1]
                if (self.edge in ("left", "right") and abs(dy) > abs(dx)) or \
                        (self.edge == "top" and abs(dx) > abs(dy)):
                    self.state, self._slide_acc, self._slide_last = "slider", 0.0, r
                    self.slider_text = SLIDER_TEXT[self.edge]
                    log(f"slider {self.edge} start")
                else:
                    self.state = "cursor"  # normal mouse use; ignore until lift
                    log(f"moved after {now - self._t0:.2f}s -> normal mouse")
            elif now - self._t0 >= HOLD_TIME:
                self.state, self.stroke = "armed", [p]
                self._cursor0 = actions.get_cursor()
                self.anchor = self._cursor0
                log("armed: draw mode")
        elif self.state == "armed":
            self.stroke.append(p)
            if math.dist(p, self.stroke[0]) > HOLD_SLOP * aspect:
                self.state = "drawing"
        elif self.state == "drawing":
            self.stroke.append(p)
        elif self.state == "slider":
            self._slide(r)

    def _slide(self, r):
        """Finger running along an edge: left = volume, right = brightness, top = tabs."""
        actions.restore_cursor(self._cursor0)  # keep the pointer still while sliding
        if self.edge == "top":
            self._slide_acc += r[0] - self._slide_last[0]
            step, up_name, down_name = TAB_STEP, "next_tab", "prev_tab"
        else:
            self._slide_acc += self._slide_last[1] - r[1]  # finger up = more
            step = SLIDE_STEP
            up_name, down_name = (("volume_up", "volume_down") if self.edge == "left"
                                  else ("brightness_up", "brightness_down"))
        self._slide_last = r
        while abs(self._slide_acc) >= step:
            name = up_name if self._slide_acc > 0 else down_name
            self._slide_acc -= step if self._slide_acc > 0 else -step
            self.slider_text = LABELS[name]
            actions.run_now(name)

    def _drag(self, down):
        """Three fingers: hold the left button and move the cursor. Lifting all fingers drops."""
        pos = {c["id"]: (c["x"], c["y"]) for c in down}
        if self.state != "drag":
            if self.state in ("hold", "armed", "drawing"):
                actions.restore_cursor(self._cursor0)
            self.state, self.stroke = "drag", []
            self._drag_last, self._drag_rem = pos, [0.0, 0.0]
            actions.mouse_down()
            log("drag start")
            return
        common = [i for i in pos if i in self._drag_last]
        if common:
            w, _ = actions.screen_size()
            gain = w * DRAG_GAIN
            dx = sum(pos[i][0] - self._drag_last[i][0] for i in common) / len(common)
            dy = sum(pos[i][1] - self._drag_last[i][1] for i in common) / len(common)
            self._drag_rem[0] += dx * gain
            self._drag_rem[1] += dy * gain / self.aspect  # pad y spans fewer mm than x
            mx, my = int(self._drag_rem[0]), int(self._drag_rem[1])
            if mx or my:
                self._drag_rem[0] -= mx
                self._drag_rem[1] -= my
                actions.move_by(mx, my)
        self._drag_last = pos

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
