"""Write mode end to end with fake fingers, fake Gemini and fake Sarvam."""
import io
import threading
import time

threading_Thread = threading.Thread  # the real one, before tests swap in an inline version

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
    handwriting.recognise = lambda png: {"text": "shari", "script": "latin", "language": "manglish",
                                         "alternatives": []}
    sarvam.manglish_to_malayalam = lambda t: "ശരി"   # ശരി
    sarvam.translate = lambda t, s, d: "Okay"
    sarvam.speak_to_file = lambda text, path: False
    writer.threading.Thread = _InlineThread
    writer._type_later = lambda text: actions.type_text(text)  # skip the small delay
    from glide import contacts
    contacts.send_targets = lambda limit=3: [("\U0001F4AC Didi", "whatsapp", "Didi Ltst")]

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
    # Manglish -> English (meaning) and Malayalam only: no voice, no send row
    assert eng.writer.choices == [("English", "Okay"), ("മലയാളം", "ശരി")]
    assert eng.writer.n_type == 2 and eng.writer.targets == {}

    # one row: left half = English, right half = Malayalam (any height)
    one(eng, 0.1, 0.8)
    assert eng.writer.highlight == 0 and typed == []
    one(eng, 0.8, 0.2)              # slide over: highlight follows, ring restarts
    assert eng.writer.highlight == 1
    time.sleep(writer.DWELL + 0.05)
    one(eng, 0.8, 0.2)
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


def _choosing_writer():
    eng, rec = make_engine({})
    w = eng.writer
    writer.threading.Thread = _InlineThread
    w.mode, w.anchor, w.choose_t0, w._last_change = "choosing", (0, 0), time.time(), time.time()
    w.choices = [("As written", "varam"), ("മലയാളം", "വരാം"),
                 ("\U0001F4AC Didi", "വരാം"), (writer.VOICE, "x"), (writer.DO_IT, "varam")]
    w.n_type, w.targets, w.written = 2, {0: ("whatsapp", "Didi Ltst")}, "varam"
    sent = []
    w._run_send = lambda kind, who, text: sent.append((kind, who, text))
    return w, sent


def _swipe(w, x0, y0, x1, y1):
    t = time.time()
    for k in range(6):
        f = k / 5
        w.feed([{"id": 0, "x": x0 + (x1 - x0) * f, "y": y0 + (y1 - y0) * f, "tip": True}], 1.6, t + k * 0.04)
    w.feed([], 1.6, t + 0.25)


def test_language_options():
    sarvam.manglish_to_malayalam = lambda t: {"varaam": "വരാം"}.get(t)
    sarvam.translate = lambda t, s, d: {"വരാം": "I will come",
                                        "ശരി": "Okay"}.get(t)
    writer.threading.Thread = threading_Thread
    assert writer.build_choices({"text": "varaam", "language": "manglish"}) == \
        [("English", "I will come"), (writer.MAL, "വരാം")]
    assert writer.build_choices({"text": "good morning", "language": "english"}) == [("English", "good morning")]
    assert writer.build_choices({"text": "ശരി", "language": "malayalam"}) == \
        [(writer.MAL, "ശരി"), ("English", "Okay")]


def test_voice_note_only_in_whatsapp_web():
    handwriting.recognise = lambda png: {"text": "varaam", "script": "latin", "language": "manglish",
                                         "alternatives": []}
    sarvam.manglish_to_malayalam = lambda t: "വരാം"
    sarvam.translate = lambda t, s, d: "I will come"
    writer.threading.Thread = _InlineThread
    for in_wa, expected in ((False, 2), (True, 3)):
        writer.in_whatsapp_web = lambda: in_wa
        eng, rec = make_engine({})
        w = eng.writer
        w.start((0, 0))
        w._read([[(0, 0), (1, 1)]])
        assert len(w.choices) == expected, w.choices
    assert w.choices[-1] == (writer.VOICE, "വരാം")  # voice note in Malayalam
    assert w.wa_contact is None  # one word: no contact, just the message


def test_whatsapp_first_word_is_the_contact():
    from glide import contacts
    contacts.load = lambda: {"didi": "Didi Ltst"}
    handwriting.recognise = lambda png: {"text": "rashid pani kazhinju", "script": "latin",
                                         "language": "manglish", "alternatives": []}
    sarvam.manglish_to_malayalam = lambda t: {"pani kazhinju": "പണി കഴിഞ്ഞു"}.get(t)
    sarvam.translate = lambda t, s, d: "Work is finished"
    writer.threading.Thread = _InlineThread
    writer.in_whatsapp_web = lambda: True
    eng, rec = make_engine({})
    w = eng.writer
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])
    assert w.wa_contact == "Rashid" and w.header == "To: Rashid"
    assert w.choices[0] == ("English", "Work is finished")
    sent = []
    w._run_send = lambda kind, who, text: sent.append((kind, who, text))
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert sent == [("whatsapp", "Rashid", "Work is finished")]
    handwriting.recognise = lambda png: {"text": "didi varaam", "script": "latin", "language": "manglish"}
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])
    assert w.wa_contact == "Didi Ltst"  # favourite nickname


def test_slant_swipes_pick_the_app():
    writer.SEND_ROW_ENABLED = True  # parked feature: still works when switched on
    from glide import contacts
    contacts.people = lambda: {"didi": {"whatsapp": "Didi Ltst", "email": ""},
                               "rashid": {"whatsapp": "", "email": "rashrahn@gmail.com"}}
    w, sent = _choosing_writer()
    _swipe(w, 0.3, 0.8, 0.7, 0.3)             # "/" drawn upwards -> mail
    assert sent == [("mail", "rashrahn@gmail.com", "English email")]
    w, sent = _choosing_writer()
    _swipe(w, 0.3, 0.2, 0.7, 0.8)             # "\" -> WhatsApp, Malayalam version
    assert sent == [("whatsapp", "Didi Ltst", "വരാം")]
    w, sent = _choosing_writer()
    _swipe(w, 0.3, 0.5, 0.8, 0.52)            # flat swipe: nothing
    assert sent == [] and w.mode == "choosing"


def test_do_it_card_runs_agent():
    from glide import agent
    eng, rec = make_engine({})
    goals, said = [], []
    agent.run = lambda goal, status, **kw: (goals.append(goal), status("⚡ Thinking"), "done")[2]
    w = eng.writer
    w.say = said.append
    writer.threading.Thread = _InlineThread
    w.mode, w.anchor, w.choose_t0 = "choosing", (0, 0), time.time()
    w.choices = [("As written", "didi varam"), (writer.DO_IT, "didi varam")]
    w._last_change = time.time()
    w.feed([{"id": 0, "x": 0.9, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.9, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert goals == ["didi varam"] and said == ["done"] and not w.active


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
    test_do_it_card_runs_agent()
    print("ok do-it card")
    test_language_options()
    print("ok language options")
    test_voice_note_only_in_whatsapp_web()
    print("ok voice only in whatsapp")
    test_whatsapp_first_word_is_the_contact()
    print("ok first word is the contact")
    test_slant_swipes_pick_the_app()
    print("ok slant swipes")
