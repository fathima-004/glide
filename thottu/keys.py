"""Find API keys in the environment, or in the user's saved variables (setx) even if
this process started before they were set."""
import os


ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _from_file(name):
    """Read NAME=value from the project's .env file (git-ignored)."""
    try:
        with open(ENV_FILE, encoding="utf-8-sig") as f:
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
