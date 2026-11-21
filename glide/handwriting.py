"""Finger handwriting -> text, read by Google's open Gemma model from an image of the strokes.

Gemma 4 is tried first. If it's overloaded or slow, Gemini Flash-Lite takes over so the
user is never left waiting, and Gemma is skipped for a couple of minutes before retrying.

    python -m glide.handwriting demo.json   # strokes from JSON, prints the result
"""
import base64
import io
import json
import re
import sys
import time

import requests
from PIL import Image, ImageDraw

from .keys import get_key

# (model, timeout seconds). Gemma first; Gemini Flash-Lite is the fast safety net.
GEMMA = [("gemma-4-26b-a4b-it", 6), ("gemma-4-31b-it", 6)]
FALLBACK = [("gemini-flash-lite-latest", 10), ("gemini-3.5-flash-lite", 10)]
GEMMA_COOLDOWN = 120  # seconds to skip Gemma after it fails
_gemma_down_until = 0.0
last_model = None      # which model read the last word (shown on screen)

PROMPT = (
    "This image is handwriting drawn with a finger on a laptop touchpad, so it is shaky. "
    "It is a short word or phrase in Malayalam script, Arabic script, or English/Latin letters "
    "(Latin letters may be Manglish, i.e. Malayalam typed in English letters). "
    "Keep punctuation exactly as written, especially a hyphen '-' (a short flat stroke, it may be "
    "on its own). "
    'Reply with ONLY this JSON, nothing else: {"text": "<exact text written>", '
    '"script": "malayalam" or "arabic" or "latin", '
    '"language": "malayalam" (Malayalam script) or "arabic" (Arabic script) or "english" '
    '(English words) or "manglish" (Malayalam words in English letters, e.g. "varam", "pani kazhinju"), '
    '"alternatives": ["<up to 2 other likely readings>"]}'
)


def strokes_to_png(strokes, height=320, pad=28, width_px=8):
    """strokes: list of lists of (x, y), any scale, y down. Returns PNG bytes."""
    pts = [p for s in strokes for p in s]
    if not pts:
        raise ValueError("no strokes")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    w, h = max(max(xs) - x0, 1e-6), max(max(ys) - y0, 1e-6)
    scale = (height - 2 * pad) / h
    if w * scale > 4 * height:  # very wide word: limit by width instead
        scale = (4 * height - 2 * pad) / w
    img_w = int(w * scale + 2 * pad)
    img_h = int(h * scale + 2 * pad)
    img = Image.new("RGB", (max(img_w, height // 2), max(img_h, height // 2)), "white")
    d = ImageDraw.Draw(img)
    for s in strokes:
        xy = [((x - x0) * scale + pad, (y - y0) * scale + pad) for x, y in s]
        if len(xy) == 1:
            x, y = xy[0]
            d.ellipse((x - width_px / 2, y - width_px / 2, x + width_px / 2, y + width_px / 2), fill="black")
        else:
            d.line(xy, fill="black", width=width_px, joint="curve")
            for x, y in (xy[0], xy[-1]):
                d.ellipse((x - width_px / 2, y - width_px / 2, x + width_px / 2, y + width_px / 2),
                          fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _parse(text):
    """Pull the JSON object out of a reply (Gemma may wrap it in ```json fences)."""
    m = re.search(r"\{.*\}", text, re.S)
    out = json.loads(m.group(0) if m else text)
    out["text"] = str(out.get("text", "")).strip().strip('"')
    out["script"] = out.get("script") or "latin"
    if any("ഀ" <= ch <= "ൿ" for ch in out["text"]):
        out["script"], out["language"] = "malayalam", "malayalam"
    elif any("؀" <= ch <= "ۿ" for ch in out["text"]):
        out["script"], out["language"] = "arabic", "arabic"
    elif out.get("language") not in ("english", "manglish"):
        out["language"] = "unknown"  # Latin letters, language unclear: offer both
    out["alternatives"] = [str(a).strip() for a in out.get("alternatives", []) if str(a).strip()]
    return out if out["text"] else None


def _ask(model, timeout, key, png_bytes):
    gen = {"temperature": 0, "thinkingConfig": {"thinkingLevel": "minimal"}}
    if model.startswith("gemini"):
        gen["responseMimeType"] = "application/json"
    body = {"contents": [{"parts": [
        {"text": PROMPT},
        {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png_bytes).decode()}},
    ]}], "generationConfig": gen}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # key in a header, never in the URL, so it can't leak into logs or error messages
    r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=timeout)
    if r.status_code == 400 and "hinking" in r.text:
        gen.pop("thinkingConfig")
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    answer = [p["text"] for p in parts if "text" in p and not p.get("thought")]
    return _parse(answer[-1])


def recognise(png_bytes):
    """Returns {"text", "script", "alternatives", "model"} or None on failure."""
    global _gemma_down_until, last_model
    key = get_key("GEMINI_API_KEY")
    if not key:
        print("handwriting: GEMINI_API_KEY not set")
        return None
    override = get_key("GLIDE_MODEL")
    models = [(override, 15)] if override else []
    if time.time() >= _gemma_down_until:
        models += GEMMA
    models += FALLBACK
    for model, timeout in models:
        if model.startswith("gemma") and time.time() < _gemma_down_until:
            continue  # the other Gemma just failed: don't wait on this one too
        try:
            out = _ask(model, timeout, key, png_bytes)
            if out:
                last_model = out["model"] = model
                return out
        except (requests.RequestException, RuntimeError, KeyError, IndexError, ValueError) as e:
            print(f"handwriting: {model} failed: {type(e).__name__} {e if isinstance(e, RuntimeError) else ''}")
            if model.startswith("gemma"):
                _gemma_down_until = time.time() + GEMMA_COOLDOWN
    return None


def ask_json(prompt, timeout=12):
    """Text-only JSON question for the agent: Gemma when it's answering, else Gemini."""
    global _gemma_down_until
    key = get_key("GEMINI_API_KEY")
    if not key:
        return None
    for model, t in GEMMA + FALLBACK:
        if model.startswith("gemma") and time.time() < _gemma_down_until:
            continue  # Gemma is busy: go straight to the safety net
        gen = {"temperature": 0, "thinkingConfig": {"thinkingLevel": "minimal"}}
        if model.startswith("gemini"):
            gen["responseMimeType"] = "application/json"
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=max(t, timeout))
            if r.status_code == 400 and "hinking" in r.text:
                gen.pop("thinkingConfig")
                r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=max(t, timeout))
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = [p["text"] for p in parts if "text" in p and not p.get("thought")][-1]
            m = re.search(r"\{.*\}", text, re.S)
            out = json.loads(m.group(0) if m else text)
            out["_model"] = model
            return out
        except (requests.RequestException, RuntimeError, KeyError, IndexError, ValueError) as e:
            print(f"ask_json: {model} failed: {type(e).__name__} {e if isinstance(e, RuntimeError) else ''}")
            if model.startswith("gemma"):
                _gemma_down_until = time.time() + GEMMA_COOLDOWN
    return None


def _health_loop():
    """Quietly ping Gemma every 90 s, so a word is only sent to Gemma when it is answering."""
    global _gemma_down_until
    while True:
        key = get_key("GEMINI_API_KEY")
        if key:
            model, _ = GEMMA[0]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                t = time.time()
                r = requests.post(url, headers={"x-goog-api-key": key}, timeout=8,
                                  json={"contents": [{"parts": [{"text": "Reply with: ok"}]}],
                                        "generationConfig": {"temperature": 0, "maxOutputTokens": 4}})
                healthy = r.ok and time.time() - t < 5
            except requests.RequestException:
                healthy = False
            _gemma_down_until = 0.0 if healthy else time.time() + GEMMA_COOLDOWN
        time.sleep(90)


def start_health_checks():
    import threading
    threading.Thread(target=_health_loop, daemon=True).start()


def model_name(model):
    """'gemma-4-26b-a4b-it' -> 'Gemma 4', 'gemini-flash-lite-latest' -> 'Gemini'."""
    if not model:
        return "Gemma"
    return "Gemma 4" if model.startswith("gemma") else "Gemini"


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        print(recognise(strokes_to_png(json.load(f))))
