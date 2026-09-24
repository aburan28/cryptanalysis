"""Exact old/new field and curve comparisons for the IC runner copy."""

import random

from common import old, new, old_curves, new_curves, OldRunnerField, NewRunnerField


rng = random.Random(20260924)
checked = 0
for m in (5, 9, 131):
    a, b = old.Onb(m), new.Onb(m)
    coords = list(range(1 << m)) if m == 5 else \
        [rng.getrandbits(m) for _ in range(128)]
    for c in coords:
        x = a.fromCoords(c)
        assert x == b.fromCoords(c)
        assert a.toCoords(x) == b.toCoords(x)
        assert a.trace(x) == b.trace(x)
        assert a.sqr(x) == b.sqr(x)
        for k in (1, 2, 7, m):
            assert a.frob(x, k) == b.frob(x, k)
            checked += 1
        checked += 4
    for _ in range(128):
        x = a.fromCoords(rng.getrandbits(m))
        y = a.fromCoords(rng.getrandbits(m))
        assert a.mul(x, y) == b.mul(x, y)
        checked += 1
    raw = [0, -1, -2, 1 << (a.n + 1)] + \
        [rng.getrandbits(a.n + 7) for _ in range(64)]
    for x in raw:
        assert a.trace(x) == b.trace(x)
        for k in (1, 2, m):
            assert a.frob(x, k) == b.frob(x, k)
            checked += 1
        checked += 1

    f0, f1 = OldRunnerField(m), NewRunnerField(m)
    c0, c1 = old_curves.Curve(f0), new_curves.Curve(f1)
    points = []
    for _ in range(48):
        x = f0.fromCoords(rng.getrandbits(m))
        p = c0.pointFromX(x)
        assert p == c1.pointFromX(x)
        assert c0.onCurve(p) == c1.onCurve(p)
        checked += 2
        if p is not None:
            points.append(p)
    for p in points[:8]:
        assert c0.dbl(p) == c1.dbl(p)
        assert c0.mul(p, 17) == c1.mul(p, 17)
        checked += 2
    for p, q in zip(points[:8], points[1:9]):
        assert c0.add(p, q) == c1.add(p, q)
        checked += 1

# The runner-only polynomial-basis view is retained and agrees on test inputs.
for m in (11, 13, 15):
    v0, v1 = old_curves.NormalView(m), new_curves.NormalView(m)
    assert v0.poly == v1.poly and v0.conj == v1.conj
    for _ in range(24):
        value = rng.getrandbits(m)
        assert v0.fromCoords(value) == v1.fromCoords(value)
        assert v0.toCoords(value) == v1.toCoords(value)
        assert v0.frob(value, 1) == v1.frob(value, 1)
        assert v0.trace(value) == v1.trace(value)
        checked += 4
print('runner exact outputs:', checked)
