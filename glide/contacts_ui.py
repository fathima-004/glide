"""The small 'Contacts for Glide Agent' window: add or remove nicknames."""
import tkinter as tk

from . import contacts

BG, CARD, FG, MUTED = "#0b1118", "#121b26", "#ffffff", "#8aa0b4"
CYAN, ORANGE = "#39f5ff", "#ffb84d"


def open_contacts_window(root):
    win = tk.Toplevel(root)
    win.title("Glide contacts")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    k = max(1.0, float(win.tk.call("tk", "scaling")) / (96 / 72))  # follow display scaling
    w, h = int(540 * k), int(600 * k)
    win.geometry(f"{w}x{h}+{(win.winfo_screenwidth() - w) // 2}+{(win.winfo_screenheight() - h) // 2}")
    win.resizable(False, False)

    tk.Label(win, text="⚡ Contacts for Glide Agent", bg=BG, fg=FG,
             font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=24, pady=(22, 2))
    tk.Label(win, text="Only needed when the WhatsApp name differs from what you write.\n"
                       "Any other name (e.g. “amma”) is searched in WhatsApp as written.",
             bg=BG, fg=MUTED, justify="left", font=("Segoe UI", 10),
             wraplength=w - int(48 * k)).pack(anchor="w", padx=24)

    form = tk.Frame(win, bg=BG)
    form.pack(fill="x", padx=24, pady=(16, 6))
    entries = {}
    for col, (key, label, example) in enumerate((("nick", "I'll write", "didi"),
                                                  ("name", "WhatsApp name", "Didi Ltst"))):
        tk.Label(form, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 10)).grid(row=0, column=col, sticky="w")
        e = tk.Entry(form, bg=CARD, fg=FG, insertbackground=FG, relief="flat",
                     font=("Nirmala UI", 12), width=14)
        e.grid(row=1, column=col, padx=(0, 10), ipady=6, sticky="we")
        e.insert(0, "")
        entries[key] = e
    msg = tk.Label(win, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
    msg.pack(anchor="w", padx=24)

    listing = tk.Frame(win, bg=BG)
    listing.pack(fill="both", expand=True, padx=24, pady=8)

    def refresh():
        for child in listing.winfo_children():
            child.destroy()
        items = sorted(contacts.load().items())
        if not items:
            tk.Label(listing, text="No nicknames yet.", bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        for nick, name in items:
            row = tk.Frame(listing, bg=CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=nick, bg=CARD, fg=ORANGE, font=("Nirmala UI", 12, "bold"),
                     width=12, anchor="w").pack(side="left", padx=(12, 4), pady=8)
            tk.Label(row, text="→  " + name, bg=CARD, fg=FG, font=("Nirmala UI", 12),
                     anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(row, text="Remove", bg=CARD, fg=MUTED, relief="flat", font=("Segoe UI", 9),
                      command=lambda n=nick: (contacts.remove(n), refresh())).pack(side="right", padx=8)

    def add(_event=None):
        nick, name = entries["nick"].get().strip(), entries["name"].get().strip()
        if not nick or not name:
            msg.configure(text="Fill in both boxes", fg=ORANGE)
            return
        contacts.add(nick, name)
        msg.configure(text=f"Added: write “{nick} …” to message {name}", fg=CYAN)
        for e in entries.values():
            e.delete(0, "end")
        entries["nick"].focus_set()
        refresh()

    tk.Button(form, text="Add", command=add, bg=CYAN, fg="#001018", relief="flat",
              font=("Segoe UI Semibold", 11), padx=14).grid(row=1, column=2, ipady=3)
    entries["name"].bind("<Return>", add)
    win.bind("<Escape>", lambda e: win.destroy())
    refresh()
    entries["nick"].focus_force()
