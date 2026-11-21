"""The small 'Favourite people' window: nickname + WhatsApp name and/or email."""
import tkinter as tk

from . import contacts

BG, CARD, FG, MUTED = "#0b1118", "#121b26", "#ffffff", "#8aa0b4"
CYAN, ORANGE = "#39f5ff", "#ffb84d"


def open_contacts_window(root):
    win = tk.Toplevel(root)
    win.title("Glide favourite people")
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    k = max(1.0, float(win.tk.call("tk", "scaling")) / (96 / 72))  # follow display scaling
    w, h = int(640 * k), int(620 * k)
    win.geometry(f"{w}x{h}+{(win.winfo_screenwidth() - w) // 2}+{(win.winfo_screenheight() - h) // 2}")
    win.resizable(False, False)

    tk.Label(win, text="\U0001F4AC Favourite people", bg=BG, fg=FG,
             font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=24, pady=(22, 2))
    tk.Label(win, text="The first 3 show up as one-touch “send to” cards after you write a message "
                       "(WhatsApp in Malayalam, or a proper English email). Fill in WhatsApp, email, or both.",
             bg=BG, fg=MUTED, justify="left", font=("Segoe UI", 10),
             wraplength=w - int(48 * k)).pack(anchor="w", padx=24)

    form = tk.Frame(win, bg=BG)
    form.pack(fill="x", padx=24, pady=(16, 6))
    entries = {}
    for col, (key, label) in enumerate((("nick", "Nickname"), ("wa", "WhatsApp name"), ("email", "Email"))):
        tk.Label(form, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 10)).grid(row=0, column=col, sticky="w")
        e = tk.Entry(form, bg=CARD, fg=FG, insertbackground=FG, relief="flat",
                     font=("Nirmala UI", 11), width=13 if key != "email" else 18)
        e.grid(row=1, column=col, padx=(0, 8), ipady=6, sticky="we")
        entries[key] = e
    msg = tk.Label(win, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
    msg.pack(anchor="w", padx=24)

    listing = tk.Frame(win, bg=BG)
    listing.pack(fill="both", expand=True, padx=24, pady=8)

    def refresh():
        for child in listing.winfo_children():
            child.destroy()
        items = list(contacts.people().items())
        if not items:
            tk.Label(listing, text="No favourites yet.", bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        for i, (nick, p) in enumerate(items):
            row = tk.Frame(listing, bg=CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=nick, bg=CARD, fg=ORANGE if i < 3 else MUTED, font=("Nirmala UI", 12, "bold"),
                     width=10, anchor="w").pack(side="left", padx=(12, 4), pady=8)
            bits = [("\U0001F4AC " + p["whatsapp"]) if p["whatsapp"] else "", ("✉ " + p["email"]) if p["email"] else ""]
            tk.Label(row, text="   ".join(b for b in bits if b), bg=CARD, fg=FG, font=("Nirmala UI", 11),
                     anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(row, text="Remove", bg=CARD, fg=MUTED, relief="flat", font=("Segoe UI", 9),
                      command=lambda n=nick: (contacts.remove(n), refresh())).pack(side="right", padx=8)

    def add(_event=None):
        nick = entries["nick"].get().strip()
        wa, email = entries["wa"].get().strip(), entries["email"].get().strip()
        if email and "@" not in email:
            email += "@gmail.com"
        if not nick or not (wa or email):
            msg.configure(text="Add a nickname and a WhatsApp name or email", fg=ORANGE)
            return
        contacts.add(nick, wa, email)
        msg.configure(text=f"Added {nick}", fg=CYAN)
        for e in entries.values():
            e.delete(0, "end")
        entries["nick"].focus_set()
        refresh()

    tk.Button(form, text="Add", command=add, bg=CYAN, fg="#001018", relief="flat",
              font=("Segoe UI Semibold", 11), padx=14).grid(row=1, column=3, ipady=3)
    entries["email"].bind("<Return>", add)
    win.bind("<Escape>", lambda e: win.destroy())
    refresh()
    entries["nick"].focus_force()
