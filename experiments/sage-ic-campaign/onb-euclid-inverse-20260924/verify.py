"""Compare the public ONB inverse and containing curve operations."""

import random

from common import old, new, curves


rng = random.Random(20260924)
checked = 0
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    assert f0.inv(0) == f1.inv(0) == 0
    checked += 1
    coords = list(range(1, 1 << m)) if m == 5 else \
        [rng.randrange(1, 1 << m) for _ in range(192)]
    for c in coords:
        a = f0.fromCoords(c)
        x = f0.inv(a)
        assert x == f1.inv(a)
        assert f1.mul(a, x) == f1.one()
        checked += 2
    raw = [1, 1 << f0.n, (1 << (f0.n + 3)) | 7]
    raw += [rng.getrandbits(f0.n + 3) for _ in range(16 if m < 131 else 4)]
    for a in raw:
        assert f0.inv(a) == f1.inv(a)
        checked += 1
    c0, c1 = curves.Curve(f0), curves.Curve(f1)
    points = []
    for _ in range(32):
        x = f0.fromCoords(rng.getrandbits(m))
        p = c0.pointFromX(x)
        assert p == c1.pointFromX(x)
        checked += 1
        if p is not None:
            points.append(p)
    for p in points[:8]:
        assert c0.dbl(p) == c1.dbl(p)
        assert c0.mul(p, 17) == c1.mul(p, 17)
        checked += 2
    for p, q in zip(points[:8], points[1:9]):
        assert c0.add(p, q) == c1.add(p, q)
        checked += 1
print('inverse and curve exact outputs:', checked)
