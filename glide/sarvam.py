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


CODECS = {
    "wav": {},  # default; instant playback with winsound
    "ogg": {"output_audio_codec": "opus", "speech_sample_rate": 24000},  # WhatsApp's voice-note format
    "mp3": {"output_audio_codec": "mp3"},
}


def speak_to_file(text, path, codec="wav"):
    """Sarvam Bulbul text-to-speech (Malayalam or English) -> audio file. True on success."""
    import base64
    lang = "ml-IN" if any("ഀ" <= ch <= "ൿ" for ch in text) else "en-IN"
    out = _post("/text-to-speech", {"text": text, "target_language_code": lang, **CODECS[codec]})
    if not out and codec == "wav":  # older API shape
        out = _post("/text-to-speech", {"inputs": [text], "target_language_code": lang})
    audios = (out or {}).get("audios") or []
    if not audios:
        return False
    with open(path, "wb") as f:
        f.write(base64.b64decode(audios[0]))
    return True


def translate(text, src, dst):
    """src/dst like 'en-IN', 'ml-IN'."""
    out = _post("/translate", {"input": text, "source_language_code": src,
                                "target_language_code": dst})
    return (out or {}).get("translated_text")
