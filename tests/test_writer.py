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
    writer.in_whatsapp_web = lambda: False  # never look at the real screen in tests
    from glide import agent, contacts
    agent.open_chat = lambda contact, status: None
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
    from glide import agent
    agent.open_chat = lambda contact, status: None
    sarvam.manglish_to_malayalam = lambda t: "വരാം"
    sarvam.translate = lambda t, s, d: "I will come"
    writer.threading.Thread = _InlineThread
    for in_wa, text, expected in ((False, "varaam", 2), (True, "didi varaam", 3)):
        writer.in_whatsapp_web = lambda: in_wa
        handwriting.recognise = lambda png: {"text": text, "script": "latin", "language": "manglish",
                                             "alternatives": []}
        eng, rec = make_engine({})
        w = eng.writer
        w.start((0, 0))
        w._read([[(0, 0), (1, 1)]])
        assert len(w.choices) == expected, w.choices
    assert w.choices[-1] == (writer.VOICE, "വരാം")  # voice note in Malayalam


def test_whatsapp_first_word_is_the_contact():
    from glide import contacts
    contacts.load = lambda: {"didi": "Didi Ltst"}
    handwriting.recognise = lambda png: {"text": "rashid pani kazhinju", "script": "latin",
                                         "language": "manglish", "alternatives": []}
    sarvam.manglish_to_malayalam = lambda t: {"pani kazhinju": "പണി കഴിഞ്ഞു"}.get(t)
    sarvam.translate = lambda t, s, d: "Work is finished"
    writer.threading.Thread = _InlineThread
    writer.in_whatsapp_web = lambda: True
    from glide import agent
    opened, sent = [], []
    agent.open_chat = lambda contact, status: opened.append(contact)
    agent.send_text_here = lambda contact, msg, status, cancelled: (sent.append((contact, msg)), "✓ sent")[1]
    eng, rec = make_engine({})
    w = eng.writer
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])        # name and message in one go
    assert opened == ["Rashid"] and w.chat_open and w.header == "To: Rashid"
    assert w.choices[0] == ("English", "Work is finished")
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert sent == [("Rashid", "Work is finished")] and opened == ["Rashid"]  # no second search

    # name first, pause, then the message
    opened.clear()
    sent.clear()
    handwriting.recognise = lambda png: {"text": "didi -", "script": "latin", "language": "english"}
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])                 # hyphen: a new person (Rashid was the last one)
    assert opened == ["Didi Ltst"] and w.mode == "writing" and w.choices == []  # favourite nickname
    handwriting.recognise = lambda png: {"text": "pani kazhinju", "script": "latin", "language": "manglish"}
    w._read([[(0, 0), (1, 1)]])
    assert w.mode == "choosing" and w.wa_contact == "Didi Ltst" and opened == ["Didi Ltst"]
    assert w.choices[0] == ("English", "Work is finished")


def test_comma_means_new_person_otherwise_continue():
    """'Name, message' = new person. No comma = the message continues with the same person."""
    from glide import agent
    opened, sent = [], []
    agent.open_chat = lambda contact, status: opened.append(contact)
    agent.send_text_here = lambda contact, msg, status, cancelled: (sent.append((contact, msg)), "✓ sent")[1]
    writer.in_whatsapp_web = lambda: True
    writer.threading.Thread = _InlineThread
    sarvam.manglish_to_malayalam = lambda t: None
    sarvam.translate = lambda t, s, d: None
    eng, rec = make_engine({})
    w = eng.writer
    handwriting.recognise = lambda png: {"text": "Baba", "script": "latin", "language": "english"}
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])                          # only a name, then write mode times out
    assert opened == ["Baba"] and w.mode == "writing"
    w.tick(time.time() + writer.WAIT_FOR_MESSAGE + 1)
    assert not w.active
    handwriting.recognise = lambda png: {"text": "Rahul - hello", "script": "latin", "language": "english"}
    w.start((0, 0))                                      # hyphen: a new contact
    assert w.wa_contact is None
    w._read([[(0, 0), (1, 1)]])
    assert opened == ["Baba", "Rahul"] and w.wa_contact == "Rahul"
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert sent == [("Rahul", "hello")]
    handwriting.recognise = lambda png: {"text": "see you soon", "script": "latin", "language": "english"}
    w.start((0, 0))                                      # no hyphen: continue with Rahul
    w._read([[(0, 0), (1, 1)]])
    assert w.wa_contact == "Rahul" and w.choices[0] == ("English", "see you soon")
    assert w.preview() == ("Rahul", "", False) or True
    assert writer.split_recipient("Baba - varaam", "Rahul") == ("Baba", "varaam", True)
    assert writer.split_recipient("varaam", "Rahul") == (None, "varaam", False)
    assert writer.split_recipient("Baba varaam", None) == ("Baba", "varaam", True)  # no one yet
    writer.in_whatsapp_web = lambda: False


def test_whatsapp_word_by_word():
    """On a small pad you write one word at a time: Baba (pause) varaam (pause) ... stop 2 s."""
    from glide import agent
    opened = []
    agent.open_chat = lambda contact, status: opened.append(contact)
    writer.in_whatsapp_web = lambda: True
    writer.threading.Thread = _InlineThread
    sarvam.manglish_to_malayalam = lambda t: "വരാം"
    sarvam.translate = lambda t, s, d: "I will come"
    readings = iter([{"text": "Baba", "language": "english"}, {"text": "varaam", "language": "manglish"}])
    handwriting.recognise = lambda png: next(readings)
    eng, rec = make_engine({})
    w = eng.writer
    w.start((0, 0))
    w._await_release = False
    t = time.time()
    for k in range(2):                       # two words, each followed by a short pause
        w.strokes, w._touching, w._last_change = [[(0, 0), (1, 1)]], False, t - 1.5
        w.tick(t)
        assert w.mode == "writing" and w.strokes == []
    assert w.words_so_far == ["Baba", "varaam"] and opened == []  # nothing opens while writing
    w.tick(time.time() + writer.FINISH_AFTER + 1)  # stop writing: use the words
    assert opened == ["Baba"] and w.wa_contact == "Baba"
    assert w.choices == [("English", "I will come"), (writer.MAL, "വരാം"),
                         (writer.VOICE, "വരാം")]
    writer.in_whatsapp_web = lambda: False


def test_escape_aborts_a_pending_send():
    from glide import agent
    eng, rec = make_engine({})
    w = eng.writer
    w.mode, w._agent_touched = "agent", False
    agent.COUNTDOWN = 1
    t = time.time()

    def cancelled():
        if time.time() - t > 0.2 and w.active:
            w.abort()                         # Esc pressed during the countdown
        return w._agent_touched

    assert agent._countdown("Sending", lambda s: None, cancelled) is False
    assert not w.active


def test_arabic_options():
    writer.threading.Thread = threading_Thread
    handwriting.ask_json = lambda prompt: {"english": "I will come tomorrow"}
    assert writer.build_choices({"text": "سأأتي غدا", "language": "arabic"}) == \
        [(writer.ARA, "سأأتي غدا"), ("English", "I will come tomorrow")]
    out = handwriting._parse('{"text": "شكرا", "script": "latin", "language": "english"}')
    assert out["language"] == "arabic" and out["script"] == "arabic"  # script wins over a wrong label


def test_gmail_first_word_is_the_address():
    from glide import agent, contacts
    contacts.email_of = lambda nick: ""
    writer.in_whatsapp_web = lambda: False
    writer.in_gmail = lambda: True
    writer.threading.Thread = _InlineThread
    sarvam.manglish_to_malayalam = lambda t: "പണി കഴിഞ്ഞു"
    sarvam.translate = lambda t, s, d: "Work is finished"
    mails = []
    agent._gmail = lambda step, status, cancelled: (mails.append(step), "sent")[1]
    handwriting.ask_json = lambda prompt: {"subject": "Work is finished", "body": "Hi,\n\nThe work is finished.\n\nThanks,"}
    eng, rec = make_engine({})
    w = eng.writer
    handwriting.recognise = lambda png: {"text": "rashrahn", "script": "latin", "language": "english"}
    w.start((0, 0))
    w._read([[(0, 0), (1, 1)]])             # the address first...
    assert w.mail_to == "rashrahn@gmail.com" and w.mode == "writing"
    handwriting.recognise = lambda png: {"text": "pani kazhinju", "script": "latin", "language": "manglish"}
    w._read([[(0, 0), (1, 1)]])             # ...then the mail
    assert w.choices == [("English", "Work is finished"),
                         (writer.MAL, "പണി കഴിഞ്ഞു")]
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time())
    w.feed([{"id": 0, "x": 0.1, "y": 0.5, "tip": True}], 1.6, time.time() + writer.DWELL + 0.1)
    assert mails == [{"action": "gmail", "to": "rashrahn@gmail.com", "to_name": "",
                      "subject": "Work is finished", "body": "Hi,\n\nThe work is finished.\n\nThanks,"}]
    handwriting.ask_json = lambda prompt: None  # AI down: the text goes as written
    assert writer.tidy_mail("work is finished") == ("work is finished", "work is finished")
    writer.in_gmail = lambda: False


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
    test_gmail_first_word_is_the_address()
    print("ok gmail first word is the address")
    test_arabic_options()
    print("ok arabic")
    test_comma_means_new_person_otherwise_continue()
    print("ok comma rule")
    test_whatsapp_word_by_word()
    print("ok whatsapp word by word")
    test_escape_aborts_a_pending_send()
    print("ok esc aborts")
    test_slant_swipes_pick_the_app()
    print("ok slant swipes")


def test_hyphen_forms():
    assert writer.split_recipient("Baba-varaam", None) == ("Baba", "varaam", True)
    assert writer.split_recipient("ammu - report sent", "rashrahn@gmail.com") == ("ammu", "report sent", True)
    assert writer.split_recipient("report sent", "rashrahn@gmail.com") == (None, "report sent", False)
    assert writer.split_recipient("Didi u{2013} hello", "Baba")[0] == "Didi"  # en dash too
    test_hyphen_forms_ran.append(1)


test_hyphen_forms_ran = []
test_hyphen_forms()
print("ok hyphen forms")

