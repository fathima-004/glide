"""Run Glide:  python -m glide          (overlay + tray icon)
               python -m glide --debug  (print finger data, no overlay)

Ctrl+Alt+T turns Glide on/off.  Ctrl+Alt+Q quits."""
import ctypes
import sys
import time

from .gestures import GestureEngine
from .touchpad import TouchpadReader


class State:
    def __init__(self, engine):
        self.enabled = True
        self.engine = engine
        self.tray = None

    def toggle(self):
        self.enabled = not self.enabled
        if self.engine.state in ("drag", "drag_lifted"):  # never leave the button stuck down
            from . import actions
            actions.mouse_up()
        self.engine.state, self.engine.stroke = "idle", []
        self.engine._say("Glide ON" if self.enabled else "Glide OFF")
        if self.tray:
            self.tray.refresh()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates
    except Exception:
        pass

    debug = "--debug" in sys.argv
    engine = GestureEngine()
    state = State(engine)

    def on_frame(contacts, aspect):
        if not state.enabled:
            return
        engine.feed(contacts, aspect)
        if debug:
            lbl = engine.pop_label()
            if lbl:
                print(">>> GESTURE:", lbl, flush=True)
            print(" | ".join(f"id{c['id']} {'DOWN' if c['tip'] else 'up  '} "
                             f"x={c['x']:.3f} y={c['y']:.3f}" for c in contacts), flush=True)

    def on_teach():
        engine.ui_request = "teach"

    def on_help():
        engine.ui_request = "cheatsheet"

    reader = TouchpadReader(on_frame, on_toggle=state.toggle, on_teach=on_teach, on_help=on_help)
    reader.start()
    reader.ready.wait(5)
    if reader.error:
        sys.exit(f"Could not open the touchpad: {reader.error}")

    if debug:
        print("Touch the touchpad... (Ctrl+C to stop)", flush=True)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            return

    try:
        from .tray import Tray
        state.tray = Tray(state)
        state.tray.start()
    except Exception as e:  # tray is a nicety; keep running without it
        print("tray unavailable:", e)

    from . import handwriting
    handwriting.start_health_checks()  # know if Gemma is up before anyone writes

    from .overlay import Overlay
    engine._say("Glide ON")
    Overlay(engine).run()


if __name__ == "__main__":
    main()
