"""Find API keys: environment, a .env file, or the user's saved variables (setx).

.env is looked for, in order:
  1. next to Glide.exe (when running the downloaded .exe)
  2. the project folder (when running from source)
  3. %APPDATA%\\Glide\\.env
Keys are never built into the .exe.
"""
import os
import sys


def env_files():
    paths = []
    if getattr(sys, "frozen", False):  # running as Glide.exe
        paths.append(os.path.join(os.path.dirname(sys.executable), ".env"))
    paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    paths.append(os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Glide", ".env"))
    return paths


def _from_file(name):
    """Read NAME=value from the first .env file that has it (git-ignored)."""
    for path in env_files():
        try:
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    k, sep, v = line.partition("=")
                    if sep and k.strip() == name:
                        v = v.strip().strip('"').strip("'")
                        if v and not v.startswith("paste"):
                            return v
        except OSError:
            pass
    return None


def get_key(name):
    val = os.environ.get(name) or _from_file(name)
    if val:
        return val.strip()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, name)
            return str(val).strip() or None
    except OSError:
        return None
