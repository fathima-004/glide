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


def _dim(hex_color, f):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (max(int(r * f), 2), max(int(g * f), 2), max(int(b * f), 2))


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
        elif wr.mode in ("choosing", "picked"):
            self._draw_cards(wr, ax, ay, now)

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    CARD_COLORS = {"As written": "#39f5ff", "English": "#39f5ff", "Translation": "#ff6fd8",
                   "Or": "#8aa0b4"}

    def _draw_cards(self, wr, ax, ay, now):
        cv = self.canvas
        n = max(len(wr.choices), 1)
        gap, cw, ch = 22, 260, 150
        total = n * cw + (n - 1) * gap
        sx = min(max(ax - total // 2, 20), self.sw - total - 20)
        top = ay - ch - 120 if ay - ch - 120 > 30 else ay + 60
        for i, (label, text) in enumerate(wr.choices):
            # cards slide up one after another
            t = min(max((now - wr.choose_t0 - i * 0.08) / 0.28, 0.0), 1.0)
            e = 1 - (1 - t) ** 3
            bx = sx + i * (cw + gap)
            by = top + (1 - e) * 50
            col = self.CARD_COLORS.get(label, GOLD)
            on = wr.highlight == i
            picked = wr.mode == "picked" and wr.picked == i
            if wr.mode == "picked" and not picked:
                continue  # only the chosen card stays
            grow = 10 if (on or picked) else 0
            if on or picked:  # glow
                self._round_rect(bx - grow - 8, by - grow - 8, bx + cw + grow + 8, by + ch + grow + 8,
                                 26, fill=_dim(col, 0.25), outline="")
            self._round_rect(bx - grow, by - grow, bx + cw + grow, by + ch + grow, 22,
                             fill="#12301a" if picked else "#0b1118",
                             outline="#7cff6b" if picked else (col if on else "#2c3a48"),
                             width=4 if (on or picked) else 2)
            # tag
            cv.create_text(bx + 18, by + 20, anchor="w", text=label, fill=col,
                           font=("Nirmala UI", 12, "bold"))
            # the word
            cv.create_text(bx + cw / 2, by + ch / 2 + 10, text=text, fill="#ffffff",
                           font=("Nirmala UI", 30 if len(text) < 10 else 20, "bold"), width=cw - 24)
            # speaker icon when audio is ready
            if i in wr.audio:
                cv.create_text(bx + cw - 20, by + 20, text="\U0001F50A", fill=col, font=("Segoe UI Emoji", 12))
            # dwell ring
            if on and wr.mode == "choosing":
                rx, ry, r = bx + cw / 2, by + ch + grow + 26, 14
                cv.create_oval(rx - r, ry - r, rx + r, ry + r, outline="#2c3a48", width=4)
                cv.create_arc(rx - r, ry - r, rx + r, ry + r, start=90, extent=-359.9 * wr.progress,
                              style="arc", outline=col, width=4)
            if picked:
                cv.create_text(bx + cw / 2, by + ch + 34, text="✓ Typed", fill="#7cff6b",
                               font=("Segoe UI Black", 18))

        if wr.mode == "choosing":
            # mini touchpad strip: shows which part of the pad picks which card
            py = top + ch + 70
            cv.create_text(sx + total / 2, py - 4, text="Rest your finger on the touchpad — stay to choose",
                           fill="#8aa0b4", font=("Segoe UI", 11))
            sy = py + 12
            for i in range(n):
                x0 = sx + i * total / n
                col = self.CARD_COLORS.get(wr.choices[i][0], GOLD)
                cv.create_rectangle(x0 + 2, sy, x0 + total / n - 2, sy + 14,
                                    fill=_dim(col, 0.6 if wr.highlight == i else 0.2), outline="")
            if wr.finger_x is not None:
                fx = sx + wr.finger_x * total
                cv.create_oval(fx - 9, sy - 2, fx + 9, sy + 16, fill="#ffffff", outline="")

    def _tick(self):
        self._draw()
        self.root.after(16, self._tick)

    def run(self):
        self._tick()
        self.root.mainloop()
