"""Tray icon near the clock: Turn on/off, Quit."""
import os

import pystray
from PIL import Image, ImageDraw


def _icon(on):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (57, 245, 255, 255) if on else (110, 120, 130, 255)
    d.rounded_rectangle((4, 12, 60, 52), radius=10, outline=color, width=5)
    d.ellipse((24, 24, 40, 40), fill=color)
    return img


class Tray:
    def __init__(self, state):
        self.state = state  # object with .enabled and .toggle()
        self.icon = pystray.Icon(
            "glide", _icon(True), "Glide (on)",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: "Turn OFF   (Ctrl+Alt+T)" if self.state.enabled
                                 else "Turn ON   (Ctrl+Alt+T)", self._toggle, default=True),
                pystray.MenuItem("Gesture cheat sheet   (Ctrl+Alt+H)",
                                 lambda: setattr(self.state.engine, "ui_request", "cheatsheet")),
                pystray.MenuItem("Teach a new shape…   (Ctrl+Alt+N)", self._teach),
                pystray.MenuItem("Quit   (Ctrl+Alt+Q)", lambda: os._exit(0)),
            ))

    def _toggle(self):
        self.state.toggle()

    def _teach(self):
        self.state.engine.ui_request = "teach"

    def refresh(self):
        self.icon.icon = _icon(self.state.enabled)
        self.icon.title = "Glide (on)" if self.state.enabled else "Glide (off)"
        self.icon.update_menu()

    def start(self):
        self.icon.run_detached()
