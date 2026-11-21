"""Gesture cheat sheet: a dark, always-on-top window listing every Glide gesture.

    python -m glide.cheatsheet          (opens it on its own)

    from glide.cheatsheet import show_cheatsheet
    show_cheatsheet()                    (from inside a running Tk app: opens a Toplevel)

The window is centred, closes on Esc, on any click, or by itself after 25 seconds.
Everything (icons included) is drawn on one tkinter Canvas, so no image files are needed.
"""
import tkinter as tk

# Palette (matches the on-screen overlay)
BG = "#0b1118"
CARD = "#121b26"
CARD_EDGE = "#1d2a38"
CYAN = "#39f5ff"
GOLD = "#ffd23f"
PINK = "#ff6fd8"
GREEN = "#7cff6b"
TEXT = "#e8f1f8"
MUTED = "#7f93a6"

EN = "Segoe UI"     # English text
ML = "Nirmala UI"   # Malayalam text

WIDTH, HEIGHT = 960, 650   # logical size at 100 % display scaling
CREDITS = "Malayalam by Sarvam AI  ·  handwriting read by Google Gemma  ·  this cheat sheet was built by Devin"
TIMEOUT_MS = 25_000        # auto-close delay
TICK_MS = 50               # countdown bar refresh

APP = "Glide"
TITLE = f"{APP} - your whole laptop, with one finger"


# --------------------------------------------------------------------------- content
# Each section: (name, colour, icon, hint, lines). A line is a list of (text, style) runs;
# style is "key" (highlighted in the section colour), "ml" (Malayalam font) or "" (plain).

SECTIONS = [
    ("DRAW", GOLD, "draw", "hold one finger still until the ring fills, then draw", [
        [("C", "key"), (" copy  ·  ", ""), ("V", "key"), (" paste  ·  ", ""),
         ("Z", "key"), (" undo  ·  ", ""), ("✓", "key"), (" Enter  ·  ", ""),
         ("○", "key"), (" screenshot", "")],
    ]),
    ("DRAG", CYAN, "drag", "slide three fingers", [
        [("Drag without pressing", "key"), ("  (lift & re-place to continue)", "")],
    ]),
    ("CORNERS", CYAN, "corners", "hold still in a corner, then lift", [
        [("↖", "key"), (" all windows  ·  ", ""), ("↗", "key"), (" switch app  ·  ", ""),
         ("↙", "key"), (" desktop  ·  ", ""), ("↘", "key"), (" right-click", "")],
    ]),
    ("EDGES", GREEN, "edges", "slide along an edge", [
        [("left", "key"), (" = volume  ·  ", ""), ("right", "key"), (" = brightness  ·  ", ""),
         ("top", "key"), (" = browser tabs", "")],
    ]),
    ("WRITE", PINK, "write", "hold two fingers still, then write a word", [
        [("Malayalam or English  →  cards:  ", ""), ("as written", "key"), ("  ·  ", ""),
         ("മലയാളം", "ml"), (" (via Sarvam)  ·  ", ""), ("translation", "key"), ("  ·  ", ""),
         ("🎤 voice note", "key")],
        [("Rest a finger on a card to hear it; stay to choose.", "")],
    ]),
    ("KEYS", GOLD, "keys", "anywhere, any time", [
        [("Ctrl+Alt+N", "key"), (" teach your own shape  ·  ", ""), ("Ctrl+Alt+H", "key"),
         (" this sheet  ·  ", ""), ("Ctrl+Alt+T", "key"), (" on / off  ·  ", ""),
         ("Ctrl+Alt+Q", "key"), (" quit", "")],
    ]),
]


# --------------------------------------------------------------------------- the window
class CheatSheet:
    """Builds and runs one cheat-sheet window on the given Tk/Toplevel."""

    def __init__(self, win):
        self.win = win
        self.closed = False
        self.jobs = []   # pending after() ids, cancelled on close
        self.ticks = 0

        # Scale the layout with the display DPI (Tk fonts in points already scale on their own).
        self.k = max(1.0, float(win.tk.call("tk", "scaling")) / (96 / 72))
        self.w, self.h = self.s(WIDTH), self.s(HEIGHT)

        self._setup_window()
        self.cv = tk.Canvas(win, width=self.w, height=self.h, bg=BG,
                            highlightthickness=0, bd=0, cursor="hand2")
        self.cv.pack()
        self._draw()

        # Close on Esc, any mouse click, or after the timeout.
        for widget in (win, self.cv):
            widget.bind("<Escape>", self.close)
            widget.bind("<Button>", self.close)
        self._after(TIMEOUT_MS, self.close)
        self._after(0, self._tick)
        self._fade_in(0.0)
        self._after(60, self.cv.focus_force)  # once mapped, take keyboard focus so Esc works

    # ---- helpers
    def s(self, v):
        """Logical pixels -> real pixels."""
        return int(round(v * self.k))

    def _after(self, ms, fn, *args):
        self.jobs.append(self.win.after(ms, fn, *args))

    def _font(self, size, bold=False, family=EN):
        return (family, size, "bold") if bold else (family, size)

    def _setup_window(self):
        win = self.win
        win.title(f"{APP} cheat sheet")
        win.configure(bg=BG)
        win.overrideredirect(True)          # borderless
        win.attributes("-topmost", True)
        x = (win.winfo_screenwidth() - self.w) // 2
        y = (win.winfo_screenheight() - self.h) // 2
        win.geometry(f"{self.w}x{self.h}+{x}+{y}")
        try:
            win.attributes("-alpha", 0.0)   # faded in by _fade_in
        except tk.TclError:
            pass

    def _fade_in(self, alpha):
        if self.closed:
            return
        try:
            self.win.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if alpha < 0.97:
            self._after(15, self._fade_in, min(alpha + 0.08, 0.97))

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        """Rounded rectangle as a smoothed polygon."""
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.cv.create_polygon(pts, smooth=True, **kw)

    def _runs(self, x, y, runs, color, size=13, max_x=None):
        """Draw text runs left to right on one line; returns the end x.

        If max_x is given and the line would overflow it, the font shrinks until it fits.
        """
        while True:
            items, end = [], x
            for text, style in runs:
                plain = style == ""
                family = ML if style == "ml" else EN
                item = self.cv.create_text(end, y, text=text, anchor="w",
                                           fill=TEXT if plain else color,
                                           font=self._font(size, not plain, family))
                items.append(item)
                end = self.cv.bbox(item)[2]
            if max_x is None or end <= max_x or size <= 9:
                return end
            self.cv.delete(*items)
            size -= 1

    # ---- layout
    def _draw(self):
        cv, s = self.cv, self.s
        cv.create_rectangle(0, 0, self.w, self.h, outline=CARD_EDGE, width=s(2))

        # Header: title + tagline
        x = self._runs(s(40), s(46), [(APP, "key")], CYAN, 24)
        self._runs(x, s(46), [(TITLE[len(APP):], "")], CYAN, 24)
        cv.create_text(s(40), s(80), anchor="w", text="Just touch. Don't press.",
                       fill=MUTED, font=self._font(12))

        # Sections stacked as full-width cards; multi-line cards are taller.
        y = s(108)
        for name, color, icon, hint, lines in SECTIONS:
            h = s(70 + 26 * (len(lines) - 1))
            self._card(y, h, name, color, icon, hint, lines)
            y += h + s(8)

        # Footer: how to close + countdown bar
        cv.create_text(self.w - s(40), s(80), anchor="e", fill=MUTED, font=self._font(10),
                       text="Esc or click to close")
        cv.create_text(self.w / 2, self.h - s(20), text=CREDITS, fill=MUTED, font=self._font(9))
        self.bar = cv.create_rectangle(0, self.h - s(4), self.w, self.h, fill=CYAN, width=0)

    def _card(self, y, h, name, color, icon, hint, lines):
        cv, s = self.cv, self.s
        x0, x1 = s(32), self.w - s(32)
        self._round_rect(x0, y, x1, y + h, s(14), fill=CARD, outline=CARD_EDGE, width=1)
        cv.create_rectangle(x0, y + s(12), x0 + s(4), y + h - s(12), fill=color, width=0)

        # Icon in a 56 x 56 box on the left
        getattr(self, "_icon_" + icon)(x0 + s(48), y + h / 2, color)

        # Heading line: NAME  hint
        tx = x0 + s(96)
        ty = y + s(22)
        item = cv.create_text(tx, ty, text=name, anchor="w", fill=color,
                              font=self._font(12, bold=True))
        cv.create_text(cv.bbox(item)[2] + s(12), ty, text=hint, anchor="w", fill=MUTED,
                       font=self._font(11))
        # Content lines
        for i, runs in enumerate(lines):
            self._runs(tx, ty + s(28 + 26 * i), runs, color, max_x=x1 - s(16))

    # ---- icons (each drawn around centre cx, cy in roughly a 56 x 56 box)
    def _pad(self, cx, cy, color, w=50, h=36):
        """A small touchpad outline."""
        s = self.s
        return self._round_rect(cx - s(w / 2), cy - s(h / 2), cx + s(w / 2), cy + s(h / 2),
                                s(7), fill=BG, outline=color, width=s(1.5))

    def _dot(self, x, y, r, color):
        self.cv.create_oval(x - r, y - r, x + r, y + r, fill=color, width=0)

    def _icon_draw(self, cx, cy, color):
        # Dwell ring three-quarters full, with a gold "C" stroke inside.
        cv, s = self.cv, self.s
        r = s(24)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=CARD_EDGE, width=s(4))
        cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-270,
                      style="arc", outline=CYAN, width=s(4))
        r = s(11)
        cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=45, extent=270,
                      style="arc", outline=color, width=s(3))

    def _icon_drag(self, cx, cy, color):
        # Three fingertips sliding right.
        cv, s = self.cv, self.s
        for dy in (-12, 0, 12):
            self._dot(cx - s(10), cy + s(dy), s(5), color)
            cv.create_line(cx - s(2), cy + s(dy), cx + s(18), cy + s(dy),
                           fill=color, width=s(2), arrow="last", arrowshape=(s(6), s(7), s(3)))

    def _icon_corners(self, cx, cy, color):
        # Touchpad with a glowing dot in each corner.
        s = self.s
        self._pad(cx, cy, color)
        for dx in (-17, 17):
            for dy in (-10, 10):
                self._dot(cx + s(dx), cy + s(dy), s(4), GOLD if (dx, dy) == (-17, -10) else color)

    def _icon_edges(self, cx, cy, color):
        # Touchpad with its left, right and top edges lit.
        cv, s = self.cv, self.s
        self._pad(cx, cy, MUTED)
        w, h = s(25), s(18)
        kw = dict(fill=color, width=s(4), capstyle="round")
        cv.create_line(cx - w, cy - h + s(7), cx - w, cy + h - s(7), **kw)
        cv.create_line(cx + w, cy - h + s(7), cx + w, cy + h - s(7), **kw)
        cv.create_line(cx - w + s(9), cy - h, cx + w - s(9), cy - h, **kw)

    def _icon_write(self, cx, cy, color):
        # Two resting fingertips and a handwritten squiggle.
        cv, s = self.cv, self.s
        self._dot(cx - s(20), cy - s(14), s(4), CYAN)
        self._dot(cx - s(10), cy - s(18), s(4), CYAN)
        pts = [(-22, 10), (-14, -4), (-8, 12), (0, -6), (6, 12), (14, -2), (22, 8)]
        flat = [v for px, py in pts for v in (cx + s(px), cy + s(py))]
        cv.create_line(*flat, fill=color, width=s(3), smooth=True, capstyle="round")

    def _icon_keys(self, cx, cy, color):
        # Two keycaps.
        cv, s = self.cv, self.s
        for dx, label in ((-13, "T"), (13, "Q")):
            x = cx + s(dx)
            self._round_rect(x - s(11), cy - s(12), x + s(11), cy + s(12), s(5),
                             fill=BG, outline=color, width=s(1.5))
            cv.create_text(x, cy, text=label, fill=color, font=self._font(11, bold=True))

    # ---- countdown + closing
    def _tick(self):
        if self.closed:
            return
        self.ticks += 1
        left = max(0.0, 1 - self.ticks * TICK_MS / TIMEOUT_MS)
        self.cv.coords(self.bar, 0, self.h - self.s(4), self.w * left, self.h)
        self._after(TICK_MS, self._tick)

    def close(self, _event=None):
        if self.closed:
            return
        self.closed = True
        for job in self.jobs:  # stop timers before the widgets disappear
            try:
                self.win.after_cancel(job)
            except tk.TclError:
                pass
        self.win.destroy()  # if win is our own Tk root, this also ends mainloop()


def show_cheatsheet():
    """Open the cheat sheet.

    Inside an app that already has a Tk root (and mainloop), this opens a Toplevel and
    returns at once. Otherwise it creates its own Tk root and blocks until the window closes.
    """
    root = getattr(tk, "_default_root", None)
    if root is not None:
        return CheatSheet(tk.Toplevel(root), )

    root = tk.Tk()
    sheet = CheatSheet(root, )
    root.mainloop()
    return sheet


def _main():
    try:  # crisp text on high-DPI screens, same as the main app
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    show_cheatsheet()


if __name__ == "__main__":
    _main()
