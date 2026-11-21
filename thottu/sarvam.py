"""Malayalam language help from Sarvam AI: Manglish -> Malayalam script, and translation."""
import requests

from .keys import get_key

BASE = "https://api.sarvam.ai"


def _post(path, body, timeout=8):
    key = get_key("SARVAM_API_KEY")
    if not key:
        print("sarvam: SARVAM_API_KEY not set")
        return None
    try:
        r = requests.post(BASE + path, json=body, timeout=timeout,
                          headers={"api-subscription-key": key})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"sarvam {path} failed: {e}")
        return None


def manglish_to_malayalam(text):
    """'sari' -> 'ശരി'"""
    out = _post("/transliterate", {"input": text, "source_language_code": "en-IN",
                                    "target_language_code": "ml-IN"})
    return (out or {}).get("transliterated_text")


def translate(text, src, dst):
    """src/dst like 'en-IN', 'ml-IN'."""
    out = _post("/translate", {"input": text, "source_language_code": src,
                                "target_language_code": dst})
    return (out or {}).get("translated_text")
