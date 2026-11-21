"""The small 'Teach a new shape' window."""
import tkinter as tk

from . import shapes

BG, CARD, FG, MUTED = "#0b1118", "#121b26", "#ffffff", "#8aa0b4"
CYAN, GOLD = "#39f5ff", "#ffd23f"


def open_teach_window(root, engine):
    win = tk.Toplevel(root)
    win.title("Teach Thottu a new shape")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    w, h = 460, 560
    win.geometry(f"{w}x{h}+{(win.winfo_screenwidth() - w) // 2}+{(win.winfo_screenheight() - h) // 2}")
    win.resizable(False, False)

    tk.Label(win, text="Teach Thottu a new shape", bg=BG, fg=FG,
             font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=24, pady=(22, 2))
    tk.Label(win, text="Pick what it should do, then draw your shape 3 times.\n"
                       "Draw it your way — Thottu learns your hand.",
             bg=BG, fg=MUTED, justify="left", font=("Segoe UI", 11)).pack(anchor="w", padx=24)

    choice = tk.IntVar(value=0)
    box = tk.Frame(win, bg=BG)
    box.pack(fill="x", padx=24, pady=14)
    for i, (label, _) in enumerate(shapes.PRESETS):
        tk.Radiobutton(box, text=label, variable=choice, value=i, bg=BG, fg=FG, selectcolor=CARD,
                       activebackground=BG, activeforeground=CYAN, font=("Segoe UI", 12),
                       anchor="w", command=lambda: _sync()).pack(fill="x", pady=1)

    hint = tk.Label(win, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
    hint.pack(anchor="w", padx=24)
    value = tk.Entry(win, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 12))
    value.pack(fill="x", padx=24, ipady=6)

    def _sync():
        label, action = shapes.PRESETS[choice.get()]
        needs = action.get("type") in ("open", "type") and not action.get("value")
        value.configure(state="normal" if needs else "disabled")
        hint.configure(text=("Website address, e.g. https://keralatourism.org" if action["type"] == "open"
                             else "Text to type, e.g. your email address") if needs else "")

    def start():
        label, action = shapes.PRESETS[choice.get()]
        action = dict(action)
        if not action.get("value") and action["type"] in ("open", "type"):
            v = value.get().strip()
            if not v:
                hint.configure(text="Please fill this in first", fg=GOLD)
                return
            if action["type"] == "open" and "://" not in v:
                v = "https://" + v
            action["value"] = v
            label = v.split("://")[-1].split("/")[0] if action["type"] == "open" else f"Type “{v[:18]}”"
        engine.start_teaching(label, action)
        engine._say(f"Teaching {label}: hold, then draw it (1/3)")
        win.destroy()

    def forget():
        shapes.remove_all()
        engine._say("Forgot all your shapes")
        win.destroy()

    row = tk.Frame(win, bg=BG)
    row.pack(fill="x", padx=24, pady=18, side="bottom")
    tk.Button(row, text="Start — draw it 3 times", command=start, bg=CYAN, fg="#001018",
              activebackground=GOLD, relief="flat", font=("Segoe UI Semibold", 12),
              padx=14, pady=8).pack(side="right")
    learned = len(shapes.load())
    tk.Button(row, text=f"Forget my {learned} shape{'s' if learned != 1 else ''}", command=forget,
              bg=CARD, fg=MUTED, relief="flat", font=("Segoe UI", 10), padx=10, pady=8,
              state="normal" if learned else "disabled").pack(side="left")
    win.bind("<Escape>", lambda e: win.destroy())
    _sync()
    win.focus_force()
