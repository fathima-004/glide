"""Check each shape is recognised even when drawn wobbly, small, or stretched."""
import math
import random

from thottu.gestures import TEMPLATES, recognise


def wobble(pts, amount, sx, sy, seed):
    rnd = random.Random(seed)
    return [(x * sx + rnd.uniform(-amount, amount), y * sy + rnd.uniform(-amount, amount))
            for x, y in pts]


def test_all_shapes():
    failures = []
    for name, tmpl in TEMPLATES:
        for seed in range(25):
            sx, sy = random.Random(seed).uniform(0.6, 1.4), random.Random(seed + 99).uniform(0.6, 1.4)
            got, score = recognise(wobble(tmpl, 0.05, sx, sy, seed))
            if got != name:
                failures.append((name, got, round(score, 3)))
    assert not failures, failures


def test_scribble_rejected_or_any():
    # A straight line should not trigger copy/paste/etc.
    got, _ = recognise([(i / 50, 0.0) for i in range(51)])
    assert got is None, got


if __name__ == "__main__":
    test_all_shapes()
    test_scribble_rejected_or_any()
    print("all gesture tests passed")
