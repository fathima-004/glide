"""Write mode end to end with fake fingers, fake Gemini and fake Sarvam."""
import io
import time

from PIL import Image

from glide import actions, gestures, handwriting, sarvam, writer
from tests.test_engine import make_engine, lift


def two(eng, x=0.5, y=0.5):
    eng.feed([{"id": 0, "x": x, "y": y, "tip": True},
              {"id": 1, "x": x + 0.1, "y": y, "tip": True}], 1.6)


def one(eng, x, y):
    eng.feed([{"id": 0, "x": x, "y": y, "tip": True}], 1.6)


def test_png_is_320_tall():
    png = handwriting.strokes_to_png([[(0, 0), (1, 1)], [(1, 0), (0, 1)]])
    assert Image.open(io.BytesIO(png)).size[1] == 320


def test_write_mode_flow_manglish():
    eng, rec = make_engine({})
    typed = []
    actions.type_text = typed.append
    handwriting.recognise = lambda png: {"text": "sari", "script": "latin", "alternatives": []}
    sarvam.manglish_to_malayalam = lambda t: "ശരി"   # ശരി
    sarvam.translate = lambda t, s, d: "ശരി"          # duplicate -> dropped
    sarvam.speak_to_file = lambda text, path: False
    writer.threading.Thread = _InlineThread
    writer._type_later = lambda text: actions.type_text(text)  # skip the small delay

    two(eng)
    time.sleep(gestures.WRITE_HOLD + 0.05)
    two(eng)
    assert eng.writer.mode == "writing"
    lift(eng)                       # release the two fingers
    for i in range(10):             # write a stroke
        one(eng, 0.3 + i * 0.03, 0.5)
    lift(eng)
    eng.writer._last_change -= 2    # pretend 2 s passed
    eng.writer.tick(time.time())
    assert eng.writer.mode == "choosing", eng.writer.mode
    assert eng.writer.choices == [("As written", "sari"),
                                  ("മലയാളം", "ശരി"),
                                  (writer.VOICE, "ശരി")]

    # 3 cards: left / middle / right thirds. Rest in the middle until the ring fills.
    one(eng, 0.2, 0.5)
    assert eng.writer.highlight == 0 and typed == []
    one(eng, 0.5, 0.5)               # slide over: highlight follows, ring restarts
    assert eng.writer.highlight == 1
    time.sleep(writer.DWELL + 0.05)
    one(eng, 0.5, 0.5)
    assert typed == ["ശരി"] and eng.writer.mode == "picked"
    eng.writer.tick(time.time() + 1)
    assert not eng.writer.active


def test_voice_card_sends_voice_note():
    eng, rec = make_engine({})
    sent = []
    w = eng.writer
    w._send_voice = lambda idx, text: sent.append(text)
    writer.threading.Thread = _InlineThread
    w.mode, w.anchor, w.choose_t0 = "choosing", (0, 0), time.time()
    w.choices = [("As written", "sari"), (writer.VOICE, "ശരി")]
    w._last_change = time.time()
    w.feed([{"id": 0, "x": 0.9, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.9, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert sent == ["ശരി"]


class _InlineThread:
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)

    def join(self, *a):
        pass


if __name__ == "__main__":
    test_png_is_320_tall()
    print("ok png")
    test_write_mode_flow_manglish()
    print("ok write flow")
    test_voice_card_sends_voice_note()
    print("ok voice card")
