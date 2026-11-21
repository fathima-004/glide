"""Build dist/Glide.exe: one file, no Python needed on the target laptop.

    pip install pyinstaller
    python build_exe.py

API keys are NOT packed in. Put a .env file next to Glide.exe:
    GEMINI_API_KEY=...
    SARVAM_API_KEY=...
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def make_icon(path):
    """Same look as the tray icon: a touchpad with a fingertip."""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 48, 240, 208), radius=40, fill=(11, 17, 24, 255), outline=(57, 245, 255, 255), width=18)
    d.ellipse((96, 96, 160, 160), fill=(57, 245, 255, 255))
    img.save(path, sizes=[(s, s) for s in sizes])


def main():
    icon = os.path.join(HERE, "build", "glide.ico")
    os.makedirs(os.path.dirname(icon), exist_ok=True)
    make_icon(icon)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", "Glide", "--icon", icon,
           "--hidden-import", "pystray._win32",  # pystray picks its backend at runtime
           "--collect-submodules", "glide",
           os.path.join(HERE, "Glide.pyw")]
    subprocess.run(cmd, check=True, cwd=HERE)
    print("built:", os.path.join(HERE, "dist", "Glide.exe"))


if __name__ == "__main__":
    main()
