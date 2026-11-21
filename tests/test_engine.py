"""Drive the gesture engine with fake finger frames; actions are recorded, not sent."""
import time

from thottu import actions, gestures


class Recorder:
    def __init__(self):
        self.calls = []


def make_engine(monkey):
    rec = Recorder()
    monkey["run"] = lambda name: rec.calls.append(name)
    monkey["run_now"] = lambda name: rec.calls.append(name)
    for k, v in monkey.items():
        setattr(actions, k, v)
    for k in ("restore_cursor", "mouse_down", "mouse_up", "move_by"):
        setattr(actions, k, lambda *a, **kw: None)
    actions.get_cursor = lambda: (500, 500)
    actions.screen_size = lambda: (1920, 1080)
    gestures.threading.Thread = _InlineThread
    return gestures.GestureEngine(), rec


class _InlineThread:
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def touch(eng, x, y, fid=0):
    eng.feed([{"id": fid, "x": x, "y": y, "tip": True}], 1.6)


def lift(eng):
    eng.feed([], 1.6)


def hold(eng, x, y):
    touch(eng, x, y)
    time.sleep(gestures.HOLD_TIME + 0.05)
    touch(eng, x, y)


def test_corner_top_right_switches_app():
    eng, rec = make_engine({})
    hold(eng, 0.95, 0.05)
    assert eng.state == "armed" and eng.corner == "tr"
    lift(eng)
    assert rec.calls == ["switch_app"], rec.calls


def test_left_edge_slide_up_is_volume_up():
    eng, rec = make_engine({})
    touch(eng, 0.03, 0.7)  # below 0.78 so it's the edge, not the bottom-left corner
    for i in range(1, 12):
        touch(eng, 0.03, 0.7 - i * 0.03)
    lift(eng)
    assert rec.calls and set(rec.calls) == {"volume_up"}, rec.calls


def test_right_edge_slide_down_is_dimmer():
    eng, rec = make_engine({})
    touch(eng, 0.97, 0.3)
    for i in range(1, 12):
        touch(eng, 0.97, 0.3 + i * 0.03)
    assert rec.calls and set(rec.calls) == {"brightness_down"}, rec.calls


def test_top_edge_slide_right_is_next_tab():
    eng, rec = make_engine({})
    touch(eng, 0.4, 0.04)
    for i in range(1, 12):
        touch(eng, 0.4 + i * 0.03, 0.04)
    assert rec.calls and set(rec.calls) == {"next_tab"}, rec.calls


def test_middle_move_is_normal_mouse():
    eng, rec = make_engine({})
    touch(eng, 0.5, 0.5)
    for i in range(1, 10):
        touch(eng, 0.5 + i * 0.02, 0.5)
    lift(eng)
    assert rec.calls == [] and eng.state == "idle"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
