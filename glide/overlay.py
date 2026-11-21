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

    def show_label(self, text, pos, seconds=None):
        seconds = seconds or max(1.4, len(text) / 12)  # long messages stay up long enough to read
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
        eng.tick(now)
        if eng.ui_request == "teach":
            eng.ui_request = None
            from .teach_ui import open_teach_window
            open_teach_window(self.root, eng)
        elif eng.ui_request == "cheatsheet":
            eng.ui_request = None
            from .cheatsheet import show_cheatsheet
            show_cheatsheet()
        elif eng.ui_request == "contacts":
            eng.ui_request = None
            from .contacts_ui import open_contacts_window
            open_contacts_window(self.root)
        if eng.teach is not None:
            n = len(eng.teach["samples"])
            self._pill(self.sw // 2, 40, f"✨ Teaching “{eng.teach['label']}” — "
                                          f"hold still, then draw your shape  ({n + 1}/3)", GOLD, size=14)

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

        elif state in ("drag", "drag_lifted"):
            self._pill(cx + 70, cy + 34, "✋ Dragging", CYAN)

        lbl = eng.pop_label()
        if lbl:
            self.show_label(lbl, eng.anchor if eng.anchor and lbl not in ("Glide ON", "Glide OFF")
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
            # no board: the ink is written straight over the screen, with a small hint above it
            if wr.mode == "reading":
                title = "Reading with Gemma…"
            elif wr.wa_contact:
                title = f"✍ Now write the message for {wr.wa_contact}"
            elif wr.in_whatsapp:
                title = "✍ Write the name, then the message"
            else:
                title = "✍ Write a word"
            self._pill(x0 + bw / 2, y0 - 6, title, "#7cff6b" if wr.wa_contact else CYAN, size=12)
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
        elif wr.mode == "agent":
            dots = "•" * (1 + int(now * 3) % 3)
            self._pill(ax, ay - 60, f"{wr.agent_status}  {dots}", "#ffb84d", size=16)

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    CARD_COLORS = {"As written": "#39f5ff", "English": "#39f5ff", "Translation": "#ff6fd8",
                   "Or": "#8aa0b4", "\U0001F3A4 Voice note": "#7cff6b", "⚡ Do it": "#ffb84d"}

    def _card_color(self, label):
        if label.startswith("\U0001F4AC"):
            return "#7cff6b"   # WhatsApp person
        if label.startswith("✉"):
            return "#ff6fd8"   # mail person
        return self.CARD_COLORS.get(label, GOLD)

    def _draw_cards(self, wr, ax, ay, now):
        """Two rows: top = what to type, bottom = send to / voice / do it."""
        cv = self.canvas
        rows = [list(range(0, wr.n_type)), list(range(wr.n_type, len(wr.choices)))]
        sizes = [(250, 132, 30), (210, 104, 20)]  # card w, h, word font size
        gap, row_gap = 18, 22
        block_h = sizes[0][1] + (row_gap + sizes[1][1] if rows[1] else 0)
        top = ay - block_h - 150 if ay - block_h - 150 > 30 else ay + 60
        pos = {}
        y = top
        for r, idxs in enumerate(rows):
            if not idxs:
                continue
            cw, ch, _ = sizes[r]
            total = len(idxs) * cw + (len(idxs) - 1) * gap
            sx = min(max(ax - total // 2, 20), self.sw - total - 20)
            for k, i in enumerate(idxs):
                pos[i] = (sx + k * (cw + gap), y, cw, ch, sizes[r][2])
            y += ch + row_gap

        if wr.header and wr.mode == "choosing":  # e.g. "To: Rashid" when writing in WhatsApp
            self._pill(ax, top - 30, "\U0001F4AC " + wr.header, "#7cff6b", size=15)
        for i, (label, text) in enumerate(wr.choices):
            bx, by0, cw, ch, fsize = pos[i]
            t = min(max((now - wr.choose_t0 - i * 0.06) / 0.28, 0.0), 1.0)  # cards slide up in turn
            by = by0 + (1 - (1 - (1 - t) ** 3)) * 50
            col = self._card_color(label)
            on = wr.highlight == i
            picked = wr.mode == "picked" and wr.picked == i
            if wr.mode == "picked" and not picked:
                continue  # only the chosen card stays
            if picked:
                # the chosen word flies from its card down to the cursor
                p = min((now - wr._picked_t) / 0.45, 1.0)
                e2 = p * p * (3 - 2 * p)
                ccx, ccy = bx + cw / 2, by + ch / 2
                if p < 1:
                    for k in range(1, 6):  # comet tail
                        q = max(e2 - k * 0.06, 0)
                        cv.create_text(ccx + (ax - ccx) * q, ccy + (ay - ccy) * q, text=text,
                                       fill=_dim(col, 0.5 - k * 0.08),
                                       font=("Nirmala UI", max(int(34 - 16 * e2) - k, 10), "bold"))
                    cv.create_text(ccx + (ax - ccx) * e2, ccy + (ay - ccy) * e2, text=text, fill="#ffffff",
                                   font=("Nirmala UI", int(34 - 16 * e2), "bold"))
                continue
            grow = 8 if on else 0
            if on:  # glow
                self._round_rect(bx - grow - 8, by - grow - 8, bx + cw + grow + 8, by + ch + grow + 8,
                                 24, fill=_dim(col, 0.25), outline="")
            self._round_rect(bx - grow, by - grow, bx + cw + grow, by + ch + grow, 20, fill="#0b1118",
                             outline=col if on else "#2c3a48", width=4 if on else 2)
            tag = cv.create_text(bx + 16, by + 18, anchor="w", text=label, fill=col,
                                 font=("Nirmala UI", 12 if i < wr.n_type else 11, "bold"))
            if i < wr.n_type and text == wr.written:  # what you wrote, read by Gemma
                from .handwriting import last_model, model_name
                badge = "· " + model_name(last_model)
            elif i < wr.n_type:  # converted by Sarvam AI
                badge = "· Sarvam AI"
            else:
                badge = ""
            if badge:
                cv.create_text(cv.bbox(tag)[2] + 8, by + 19, anchor="w", text=badge,
                               fill="#8aa0b4", font=("Segoe UI", 9))
            cv.create_text(bx + cw / 2, by + ch / 2 + 10, text=text, fill="#ffffff",
                           font=("Nirmala UI", fsize if len(text) < 10 else max(fsize - 10, 14), "bold"),
                           width=cw - 20)
            if i in wr.audio:
                cv.create_text(bx + cw - 18, by + 18, text="\U0001F50A", fill=col, font=("Segoe UI Emoji", 11))
            if on and wr.mode == "choosing":  # dwell ring
                rx, ry, r = bx + cw - 22, by + ch - 22, 11
                cv.create_oval(rx - r, ry - r, rx + r, ry + r, outline="#2c3a48", width=4)
                cv.create_arc(rx - r, ry - r, rx + r, ry + r, start=90, extent=-359.9 * wr.progress,
                              style="arc", outline=col, width=4)

        if wr.mode == "choosing":
            # mini touchpad: top half = top row, bottom half = bottom row, plus the finger dot
            pw, ph = 200, 70 if rows[1] else 36
            px = ax - pw / 2
            py = y + 6
            self._round_rect(px - 4, py - 4, px + pw + 4, py + ph + 4, 10, fill="#0b1118", outline="#2c3a48")
            for r, idxs in enumerate(rows):
                if not idxs:
                    continue
                rh = ph / (2 if rows[1] else 1)
                ry0 = py + r * rh
                for k, i in enumerate(idxs):
                    x0 = px + k * pw / len(idxs)
                    cv.create_rectangle(x0 + 2, ry0 + 2, x0 + pw / len(idxs) - 2, ry0 + rh - 2, outline="",
                                        fill=_dim(self._card_color(wr.choices[i][0]), 0.65 if wr.highlight == i else 0.18))
            if wr.finger_x is not None:
                fx = px + wr.finger_x * pw
                fy = py + (wr.finger_y or 0.25) * ph
                cv.create_oval(fx - 7, fy - 7, fx + 7, fy + 7, fill="#ffffff", outline="")
            if rows[1]:
                hint = ("Rest a finger — top half: type it · bottom half: send"
                        "     or swipe   /  mail   ·   \\  WhatsApp")
            else:
                hint = "Rest a finger on the touchpad — stay to choose"
            self._pill(ax, py + ph + 26, hint, "#8aa0b4", size=11)

    def _tick(self):
        self._draw()
        self.root.after(16, self._tick)

    def run(self):
        self._tick()
        self.root.mainloop()
