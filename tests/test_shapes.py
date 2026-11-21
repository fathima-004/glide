"""Teaching your own shape: 3 samples -> learned -> recognised and run."""
import math
import os
import random
import tempfile
import time

from thottu import gestures, shapes
from tests.test_engine import make_engine, lift


def w_shape(seed, jitter=0.02):
    rnd = random.Random(seed)
    pts = []
    corners = [(0, 0), (0.25, 1), (0.5, 0.3), (0.75, 1), (1, 0)]
    for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
        for i in range(15):
            t = i / 15
            pts.append((x0 + (x1 - x0) * t + rnd.uniform(-jitter, jitter),
                        y0 + (y1 - y0) * t + rnd.uniform(-jitter, jitter)))
    return pts


def draw(eng, pts):
    eng.feed([{"id": 0, "x": 0.4, "y": 0.4, "tip": True}], 1.6)
    time.sleep(gestures.HOLD_TIME + 0.05)
    eng.feed([{"id": 0, "x": 0.4, "y": 0.4, "tip": True}], 1.6)
    for x, y in pts:  # pad coords: shape drawn in a 0.4 x 0.4 area
        eng.feed([{"id": 0, "x": 0.4 + x * 0.4 / 1.6, "y": 0.4 + y * 0.4, "tip": True}], 1.6)
    lift(eng)


def test_teach_then_use():
    shapes.PATH = os.path.join(tempfile.mkdtemp(), "shapes.json")
    shapes._shapes = None
    eng, rec = make_engine({})
    ran = []
    shapes.run = lambda shape: ran.append(shape["label"])
    said = []
    eng._say = said.append

    eng.start_teaching("WhatsApp", {"type": "open", "value": "whatsapp:"})
    for seed in range(3):
        draw(eng, w_shape(seed))
    assert eng.teach is None and said[-1].startswith("Learned"), said
    assert len(shapes.load()) == 1

    draw(eng, w_shape(42))
    assert ran == ["WhatsApp"], (ran, said)

    # a circle started at the top, like people draw it
    draw(eng, [(0.5 + 0.5 * math.sin(-a / 30 * 2 * math.pi), 0.5 - 0.5 * math.cos(a / 30 * 2 * math.pi))
               for a in range(31)])
    assert ran == ["WhatsApp"] and said[-1] == "Screenshot", said  # built-ins still work


if __name__ == "__main__":
    test_teach_then_use()
    print("ok teach then use")
