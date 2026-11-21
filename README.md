# Glide — your whole laptop, with one finger

> *Just touch. Don't press.*

Laptops are built for two healthy hands: every shortcut (Ctrl+C, Alt+Tab, Win+Shift+S)
needs two hands, and dragging needs you to press hard and move at the same time.
Glide reads the raw finger data your Windows precision touchpad already produces and
turns it into one-finger gestures, with no new hardware.

Built at **HackaThoni 2026** (Alappuzha) · Track 03: Beyond the Screen (gesture / sensor control).

## Run

Windows 10/11 with a precision touchpad, Python 3.10+.

```
pip install -r requirements.txt   # tray icon (once)
python -m glide                  # run (or double-click Glide.bat)
python -m glide --debug          # print raw finger data
```

- **Ctrl + Alt + T** turns Glide on / off (also from the tray icon near the clock)
- **Ctrl + Alt + Q** quits

For three-finger drag, set Windows **Settings → Bluetooth & devices → Touchpad →
Three-finger gestures → Swipes** to **Nothing**.

## Gestures

| Do this | Get |
|---|---|
| Hold one finger still (ring fills), then draw **C** | Copy |
| … draw **V** | Paste |
| … draw **Z** | Undo |
| … draw **✓** | Enter |
| … draw **○** | Screenshot |
| Slide with three fingers | Drag, no pressing |
| Hold still in a **corner**, then lift | ↖ all windows · ↗ switch app · ↙ desktop · ↘ right-click |
| Slide along the **left edge** | Volume |
| Slide along the **right edge** | Brightness |
| Slide along the **top edge** | Previous / next tab |
| Hold **two fingers** still, then write a word | Choose: as written · Malayalam (from Manglish) · translation |

Write mode reads your finger handwriting with **Gemini** and uses **Sarvam AI** for
Malayalam: Manglish → Malayalam script (`sari` → ശരി) and Malayalam ↔ English translation.
Set keys once: `setx GEMINI_API_KEY ...` and `setx SARVAM_API_KEY ...`.

Feedback appears right at the mouse cursor, so it's where you're already looking.

## Status

- [x] Read raw multi-finger contacts (Win32 Raw Input + hid.dll)
- [x] On-screen feedback at the cursor (hold ring, glowing drawn shape, labels)
- [x] Draw-to-shortcut: C copy · V paste · Z undo · ✓ enter · ○ screenshot
- [x] Three-finger drag, no pressing
- [x] On/off toggle, tray icon, double-click launcher
- [x] Corner actions + edge sliders (volume, brightness, tabs)
- [x] Write Malayalam / English with your finger, Sarvam conversion, pick from 3 choices
- [ ] Teach your own shape
