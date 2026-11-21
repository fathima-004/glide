"""Run Thottu:  python -m thottu          (overlay)
               python -m thottu --debug  (print finger data, no overlay)"""
import ctypes
import queue
import sys
import time

from .touchpad import TouchpadReader


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates
    except Exception:
        pass

    debug = "--debug" in sys.argv
    frames = queue.Queue()

    def on_frame(contacts, aspect):
        if debug:
            print(" | ".join(f"id{c['id']} {'DOWN' if c['tip'] else 'up  '} "
                             f"x={c['x']:.3f} y={c['y']:.3f}" for c in contacts), flush=True)
        else:
            frames.put((contacts, aspect))

    reader = TouchpadReader(on_frame)
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

    from .overlay import Overlay
    Overlay(frames).run()


if __name__ == "__main__":
    main()
