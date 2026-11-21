"""Find API keys in the environment, or in the user's saved variables (setx) even if
this process started before they were set."""
import os


def get_key(name):
    val = os.environ.get(name)
    if val:
        return val.strip()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, name)
            return str(val).strip() or None
    except OSError:
        return None
