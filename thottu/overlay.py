"""Glowing finger-trail overlay so the audience can see what's drawn on the touchpad.

A full-screen, transparent, click-through, always-on-top Tk window. A "pad"
panel in the bottom-right mirrors the touchpad: finger dots plus fading trails.
"""
import ctypes
import queue
import time
import tkinter as tk

KEY = "#010101"  # transparent colour key
FINGER_COLORS = ["#39f5ff", "#ff4fd8", "#ffd23f", "#7cff6b", "#ff8a3d"]
TRAIL_LEN = 60
FADE_AFTER = 1.2  # seconds after last touch before the pad hides

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def _dim(hex_color, f):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (max(int(r * f), 2), max(int(g * f), 2), max(int(b * f), 2))


class Overlay:
    def __init__(self, frames: "queue.Queue", on_tick=None):
        self.frames = frames
        self.on_tick = on_tick
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.sw, self.sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{self.sw}x{self.sh}+0+0")
        self.canvas = tk.Canvas(self.root, bg=KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self._make_click_through()

        self.aspect = 1.6
        self.trails = {}  # contact id -> list of (x, y)
        self.live = []
        self.last_touch = 0.0
        self.label = ""
        self.label_until = 0.0

    def _make_click_through(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def show_label(self, text, seconds=1.5):
        """Big caption above the pad, e.g. 'Copied' after drawing C."""
        self.label, self.label_until = text, time.time() + seconds

    def _pad_rect(self):
        w = int(self.sw * 0.30)
        h = int(w / self.aspect)
        m = int(self.sw * 0.02)
        x0, y0 = self.sw - w - m, self.sh - h - m - 40  # stay above the taskbar
        return x0, y0, x0 + w, y0 + h

    def _drain(self):
        while True:
            try:
                contacts, aspect = self.frames.get_nowait()
            except queue.Empty:
                break
            self.aspect = aspect
            self.live = [c for c in contacts if c["tip"]]
            if self.live:
                self.last_touch = time.time()
            live_ids = set()
            for c in self.live:
                live_ids.add(c["id"])
                t = self.trails.setdefault(c["id"], [])
                t.append((c["x"], c["y"]))
                del t[:-TRAIL_LEN]
            for cid in list(self.trails):
                if cid not in live_ids:
                    # let lifted trails shrink away instead of vanishing
                    self.trails[cid] = self.trails[cid][3:]
                    if not self.trails[cid]:
                        del self.trails[cid]

    def _draw(self):
        cv = self.canvas
        cv.delete("all")
        now = time.time()
        visible = (now - self.last_touch) < FADE_AFTER or self.trails
        if visible:
            x0, y0, x1, y1 = self._pad_rect()
            cv.create_rectangle(x0, y0, x1, y1, outline="#3a4a5c", width=2, fill="#0b1118")
            cv.create_text(x0 + 12, y0 + 12, anchor="nw", text="THOTTU", fill="#56708a",
                           font=("Segoe UI Semibold", 11))
            w, h = x1 - x0, y1 - y0
            for i, (cid, pts) in enumerate(sorted(self.trails.items())):
                col = FINGER_COLORS[i % len(FINGER_COLORS)]
                xy = [(x0 + px * w, y0 + py * h) for px, py in pts]
                if len(xy) > 1:
                    flat = [v for p in xy for v in p]
                    cv.create_line(*flat, fill=_dim(col, 0.35), width=14, capstyle="round",
                                   joinstyle="round", smooth=True)
                    cv.create_line(*flat, fill=col, width=4, capstyle="round",
                                   joinstyle="round", smooth=True)
            for i, c in enumerate(sorted(self.live, key=lambda c: c["id"])):
                col = FINGER_COLORS[i % len(FINGER_COLORS)]
                cx, cy = x0 + c["x"] * w, y0 + c["y"] * h
                cv.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, outline=_dim(col, 0.5), width=6)
                cv.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=col, outline="")
        if self.label and now < self.label_until:
            x0, y0, x1, _ = self._pad_rect()
            cv.create_text((x0 + x1) / 2, y0 - 34, text=self.label, fill="#ffffff",
                           font=("Segoe UI Black", 26))

    def _tick(self):
        self._drain()
        if self.on_tick:
            self.on_tick(self)
        self._draw()
        self.root.after(16, self._tick)

    def run(self):
        self._tick()
        self.root.mainloop()
