"""On-screen feedback, drawn right at the mouse cursor (where you're already looking).

- Holding still: a ring around the cursor fills up -> draw mode
- Drawing: your shape appears in glowing gold at the cursor
- After: a big word ("Copied") pops up at the cursor
- Three-finger drag: a "Dragging" tag follows the cursor

A full-screen, transparent, click-through, always-on-top Tk window.
"""
import ctypes
import time
import tkinter as tk

from . import actions
from .gestures import CORNERS, HOLD_TIME, LABELS

KEY = "#010101"  # transparent colour key
GOLD, GOLD_GLOW = "#ffd23f", "#5c4a10"
CYAN = "#39f5ff"
SHAPE_SIZE = 0.45  # drawn shape height as a fraction of screen height (pad height -> this)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


class Overlay:
    def __init__(self, engine):
        self.engine = engine
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
        self.label, self.label_until, self.label_pos = "", 0.0, (0, 0)

    def _make_click_through(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def show_label(self, text, pos, seconds=1.4):
        self.label, self.label_pos, self.label_until = text, pos, time.time() + seconds

    def _pill(self, x, y, text, color, size=13):
        t = self.canvas.create_text(x, y, text=text, fill=color, font=("Segoe UI Semibold", size))
        x0, y0, x1, y1 = self.canvas.bbox(t)
        r = self.canvas.create_rectangle(x0 - 10, y0 - 5, x1 + 10, y1 + 5, fill="#0b1118",
                                         outline=color, width=2)
        self.canvas.tag_raise(t, r)

    def _draw(self):
        cv, eng = self.canvas, self.engine
        cv.delete("all")
        now = time.time()
        cx, cy = actions.get_cursor()
        state = eng.state
        wr = eng.writer
        wr.tick(now)

        if wr.active:
            self._draw_writer(wr, now)
        elif state == "hold" or (state == "armed" and eng.corner):
            frac = min((now - eng._t0) / HOLD_TIME, 1.0)
            if frac > 0.15:  # don't flash on every normal touch
                r = 26
                cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#3a4a5c", width=5)
                cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-359.9 * frac,
                              style="arc", outline=GOLD, width=5)
                if eng.corner:
                    text = LABELS[CORNERS[eng.corner]]
                    self._pill(cx, cy - 56, ("Lift: " + text) if state == "armed" else text,
                               GOLD if state == "armed" else "#8aa0b4")

        elif state == "slider":
            self._pill(cx, cy - 50, eng.slider_text, CYAN, size=16)

        elif state in ("armed", "drawing"):
            ax, ay = eng.anchor or (cx, cy)
            stroke = list(eng.stroke)
            scale = self.sh * SHAPE_SIZE
            if stroke:
                sx, sy = stroke[0]
                pts = [(ax + (px - sx) * scale, ay + (py - sy) * scale) for px, py in stroke]
                if len(pts) > 1:
                    flat = [v for p in pts for v in p]
                    cv.create_line(*flat, fill=GOLD_GLOW, width=24, capstyle="round",
                                   joinstyle="round", smooth=True)
                    cv.create_line(*flat, fill=GOLD, width=8, capstyle="round",
                                   joinstyle="round", smooth=True)
                ex, ey = pts[-1]
                cv.create_oval(ex - 10, ey - 10, ex + 10, ey + 10, fill="#ffffff", outline="")
            self._pill(ax, ay - 46, "DRAW A SHORTCUT", GOLD)

        elif state == "drag":
            self._pill(cx + 70, cy + 34, "✋ Dragging", CYAN)

        lbl = eng.pop_label()
        if lbl:
            self.show_label(lbl, eng.anchor if eng.anchor and lbl not in ("Thottu ON", "Thottu OFF")
                            else (self.sw // 2, self.sh // 2))
        if self.label and now < self.label_until:
            x, y = self.label_pos
            self._pill(x, y - 60, self.label, "#ffffff", size=26)

    def _draw_writer(self, wr, now):
        cv = self.canvas
        ax, ay = wr.anchor or (self.sw // 2, self.sh // 2)
        bh = int(self.sh * 0.32)
        bw = int(bh * (self.engine.aspect or 1.6))
        x0 = min(max(ax - bw // 2, 20), self.sw - bw - 20)
        y0 = ay - bh - 70 if ay - bh - 70 > 20 else ay + 50
        if wr.mode in ("writing", "reading"):
            cv.create_rectangle(x0, y0, x0 + bw, y0 + bh, fill="#0b1118", outline=CYAN, width=3)
            title = "✍ WRITE A WORD  (Malayalam or English)" if wr.mode == "writing" \
                else "Reading…"
            cv.create_text(x0 + 14, y0 + 12, anchor="nw", text=title, fill=CYAN,
                           font=("Segoe UI Semibold", 13))
            a = self.engine.aspect or 1.6
            for s in list(wr.strokes):
                pts = [(x0 + px / a * bw, y0 + py * bh) for px, py in list(s)]
                if len(pts) > 1:
                    flat = [v for p in pts for v in p]
                    cv.create_line(*flat, fill="#0f4a52", width=16, capstyle="round",
                                   joinstyle="round", smooth=True)
                    cv.create_line(*flat, fill="#ffffff", width=6, capstyle="round",
                                   joinstyle="round", smooth=True)
                elif pts:
                    x, y = pts[0]
                    cv.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#ffffff", outline="")
        elif wr.mode == "choosing":
            n = len(wr.choices)
            gap = 16
            cw = min(320, (self.sw - 80) // max(n, 1) - gap)
            total = n * cw + (n - 1) * gap
            sx = min(max(ax - total // 2, 20), self.sw - total - 20)
            cy = ay - 110 if ay > 200 else ay + 90
            cv.create_text(sx, cy - 62, anchor="w", fill="#8aa0b4", font=("Segoe UI", 12),
                           text="Hold a finger on the left / middle / right of the touchpad, then lift")
            for i, (label, text) in enumerate(wr.choices):
                bx = sx + i * (cw + gap)
                on = wr.highlight == i
                cv.create_rectangle(bx, cy - 44, bx + cw, cy + 44, fill="#1d2a12" if on else "#0b1118",
                                    outline=GOLD if on else "#3a4a5c", width=4 if on else 2)
                cv.create_text(bx + cw / 2, cy - 22, text=label.upper(), fill="#8aa0b4",
                               font=("Segoe UI Semibold", 10))
                cv.create_text(bx + cw / 2, cy + 10, text=text, fill="#ffffff",
                               font=("Nirmala UI", 22, "bold"), width=cw - 16)

    def _tick(self):
        self._draw()
        self.root.after(16, self._tick)

    def run(self):
        self._tick()
        self.root.mainloop()
