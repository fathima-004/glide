# Glide — your whole laptop, with one finger

> *Just touch. Don't press.*

Laptops are built for two healthy hands: every shortcut (Ctrl+C, Alt+Tab, Win+Shift+S)
needs two hands, and dragging needs you to press hard and move at the same time.
Glide reads the raw finger data your Windows precision touchpad already produces and
turns it into one-finger gestures, with no new hardware.

Built at **HackaThoni 2026** (Alappuzha) · Track 03: Beyond the Screen (gesture / sensor control).

## Download (no Python needed)

1. Download **Glide.exe** from the [latest release](https://github.com/fathima-004/glide/releases/latest).
2. Put a file named `.env` in the same folder, with your keys (only needed for write mode):
   ```
   GEMINI_API_KEY=...
   SARVAM_API_KEY=...
   ```
3. Double-click **Glide.exe**. Windows may say "Windows protected your PC" because the app isn't
   signed: click **More info → Run anyway**.

Needs Windows 10/11 and a precision touchpad (almost every laptop from the last few years).

## Run from source

Python 3.10+. Build the .exe yourself with `python build_exe.py`.

```
pip install -r requirements.txt   # tray icon (once)
python -m glide                  # run (or double-click Glide.bat)
python -m glide --debug          # print raw finger data
```

- **Ctrl + Alt + T** turns Glide on / off (also from the tray icon near the clock)
- **Ctrl + Alt + H** shows the gesture cheat sheet (also `python -m glide.cheatsheet`)
- **Ctrl + Alt + N** teaches Glide a new shape
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
| Hold **two fingers** still, then write a word | Cards: as written · മലയാളം · translation · 🎤 voice note |
| **Ctrl+Alt+N**, pick an action, draw your own shape 3× | Your shape now does that (e.g. **W** → WhatsApp) |

Feedback appears right at the mouse cursor, so it's where you're already looking.

Put API keys in a `.env` file next to this README (it is git-ignored):

```
GEMINI_API_KEY=...
SARVAM_API_KEY=...
```

## Built with

| | What it does in Glide |
|---|---|
| **[Sarvam AI](https://www.sarvam.ai)** | All the Malayalam: **transliterate** (Manglish → Malayalam script, `varam` → വരാം), **translate** (Malayalam ↔ English), and **Bulbul text-to-speech** — each choice card is read aloud, and the 🎤 card turns your written word into a Malayalam voice note for WhatsApp. |
| **[Devin](https://devin.ai)** (Cognition) | Built the gesture **cheat sheet** ([`glide/cheatsheet.py`](glide/cheatsheet.py), PR #1) in parallel while the gestures were being built, and picked up the mid-hackathon rename on its own. |
| **Google Gemma 4** (open model) | Reads finger handwriting (Malayalam or English) from an image of the strokes. If Gemma is overloaded or slow, Gemini Flash-Lite takes over automatically (~2 s) so the user is never stuck; each card shows which model read the word. |
| **Win32 Raw Input + hid.dll** | Raw multi-finger data from the precision touchpad — no drivers, no extra hardware. |
| **Claude Code** | Pair-programmed the app overnight. |

## Author

Made by **[@fathima-004](https://github.com/fathima-004)** at HackaThoni 2026, on a houseboat in Alappuzha.

## Status

- [x] Read raw multi-finger contacts (Win32 Raw Input + hid.dll)
- [x] On-screen feedback at the cursor (hold ring, glowing drawn shape, labels)
- [x] Draw-to-shortcut: C copy · V paste · Z undo · ✓ enter · ○ screenshot
- [x] Three-finger drag, no pressing
- [x] On/off toggle, tray icon, double-click launcher
- [x] Corner actions + edge sliders (volume, brightness, tabs)
- [x] Write Malayalam / English with your finger, Sarvam conversion, spoken cards, voice note
- [x] Teach your own shape
- [x] Gesture cheat sheet (by Devin)
