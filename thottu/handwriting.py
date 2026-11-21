"""Finger handwriting -> text, using Gemini to read an image of the strokes.

    python -m thottu.handwriting demo.json   # strokes from JSON, prints the result
"""
import base64
import io
import json
import sys

import requests
from PIL import Image, ImageDraw

from .keys import get_key

MODELS = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]  # fast ones; tested on 21 Nov 2026
PROMPT = (
    "This image is handwriting drawn with a finger on a laptop touchpad, so it is shaky. "
    "It is a short word or phrase in either Malayalam script or English/Latin letters "
    "(Latin letters may be Manglish, i.e. Malayalam typed in English letters). "
    'Reply as JSON: {"text": "<exact text written>", "script": "malayalam" or "latin", '
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


def recognise(png_bytes, timeout=10):
    """Returns {"text", "script", "alternatives"} or None on failure."""
    key = get_key("GEMINI_API_KEY")
    if not key:
        print("handwriting: GEMINI_API_KEY not set")
        return None
    models = [m for m in [get_key("GEMINI_MODEL")] if m] + MODELS
    body = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png_bytes).decode()}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0,
                             "thinkingConfig": {"thinkingLevel": "minimal"}},  # ~2 s instead of ~8 s
    }
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            # key in a header, never in the URL, so it can't leak into logs or error messages
            r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=timeout)
            if r.status_code == 400 and "hinking" in r.text:
                b2 = {**body, "generationConfig": {k: v for k, v in body["generationConfig"].items()
                                                   if k != "thinkingConfig"}}
                r = requests.post(url, headers={"x-goog-api-key": key}, json=b2, timeout=timeout)
            if r.status_code in (404, 429, 503):
                print(f"handwriting: {model} unavailable ({r.status_code}), trying next")
                continue
            if not r.ok:
                print(f"handwriting: {model} HTTP {r.status_code}: {r.text[:120]}")
                continue
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(text)
            out["text"] = str(out.get("text", "")).strip().strip('"')
            out["script"] = out.get("script") or "latin"
            out["alternatives"] = [str(a).strip() for a in out.get("alternatives", []) if str(a).strip()]
            return out if out["text"] else None
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            print(f"handwriting: {model} failed: {type(e).__name__}")
    return None


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        print(recognise(strokes_to_png(json.load(f))))
