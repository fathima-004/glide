# Thottu â€” your whole laptop, with one finger

> *Just touch. Don't press.*

Laptops are built for two healthy hands: every shortcut (Ctrl+C, Alt+Tab, Win+Shift+S)
needs two hands, and dragging needs you to press hard and move at the same time.
Thottu reads the raw finger data your Windows precision touchpad already produces and
turns it into one-finger gestures, with no new hardware.

Built at **HackaThoni 2026** (Alappuzha) Â· Track 03: Beyond the Screen (gesture / sensor control).

## Run

Windows 10/11 with a precision touchpad, Python 3.10+. No packages needed yet.

```
python -m thottu           # glowing finger-trail overlay
python -m thottu --debug   # print raw finger data
```

Or double-click `Thottu.bat`. Install the tray icon libraries once: `pip install -r requirements.txt`.

- **Ctrl + Alt + T** turns Thottu on / off (also from the tray icon near the clock)
- **Ctrl + Alt + Q** quits

## Status

- [x] Read raw multi-finger contacts (Win32 Raw Input + hid.dll)
- [x] Glowing on-screen trail so an audience can see the touchpad
- [x] Draw-to-shortcut: hold a finger still, then draw
      C copy Â· V paste Â· Z undo Â· âœ“ enter Â· â—‹ screenshot
- [x] Three-finger drag, no pressing (set Windows three-finger swipes to "Nothing")
- [ ] Corner taps + edge sliders
- [ ] Write Malayalam / English with your finger

