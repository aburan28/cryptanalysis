"""Alternating paired public-ONB inverse and containing curve benchmark."""

import hashlib
import json
import random
import statistics
import time

from common import old, new, curves


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    result = None
    for _ in range(repeat):
        result = [fn(value) for value in values]
    return time.perf_counter_ns() - start, result


def paired(case, degree, fn0, fn1, values, repeat):
    expected = [fn0(x) for x in values]
    assert expected == [fn1(x) for x in values]
    pairs = []
    for i in range(9):
        a, b = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        ta, ra = timed(a, values, repeat)
        tb, rb = timed(b, values, repeat)
        assert ra == rb == expected
        pairs.append((ta, tb) if i % 2 == 0 else (tb, ta))
    return {'case': case, 'degree': degree, 'inputs': len(values),
            'input_sha256': hashlib.sha256(json.dumps(values).encode()).hexdigest(),
            'rounds': 9, 'repeat': repeat, 'pairs': pairs,
            'paired_speedup': statistics.median(a / b for a, b in pairs)}


rng = random.Random(20260924)
rows = []
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = [f0.fromCoords(rng.randrange(1, 1 << m)) for _ in range(32)]
    rows.append(paired('inv', m, f0.inv, f1.inv, values, 4))
f0, f1 = old.Onb(131), new.Onb(131)
c0, c1 = curves.Curve(f0), curves.Curve(f1)
xs = [f0.fromCoords(rng.getrandbits(131)) for _ in range(24)]
points = [p for p in (c0.pointFromX(x) for x in xs) if p is not None]
assert len(points) >= 5
rows.append(paired('point_from_x', 131, c0.pointFromX, c1.pointFromX, xs, 2))
rows.append(paired('point_dbl', 131, c0.dbl, c1.dbl, points, 2))
print(json.dumps(rows, indent=2))
