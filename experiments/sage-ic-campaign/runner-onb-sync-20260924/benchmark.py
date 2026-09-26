"""Paired CPU timings for the actual IC runner field and curve copies."""

import hashlib
import json
import random
import statistics
import time

from common import old, new, old_curves, new_curves, OldRunnerField, NewRunnerField


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    result = None
    for _ in range(repeat):
        result = [fn(value) for value in values]
    return time.perf_counter_ns() - start, result


def paired(name, fn0, fn1, values, repeat):
    expected = [fn0(value) for value in values]
    assert expected == [fn1(value) for value in values]
    pairs = []
    for i in range(7):
        first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        ta, ra = timed(first, values, repeat)
        tb, rb = timed(second, values, repeat)
        assert ra == rb == expected
        pairs.append((ta, tb) if i % 2 == 0 else (tb, ta))
    return {'case': name, 'inputs': len(values), 'repeat': repeat, 'rounds': 7,
            'pairs': pairs, 'paired_speedup': statistics.median(a / b for a, b in pairs),
            'input_sha256': hashlib.sha256(json.dumps(values).encode()).hexdigest()}


rng = random.Random(20260924)
f0, f1 = old.Onb(131), new.Onb(131)
values = [f0.fromCoords(rng.getrandbits(131)) for _ in range(48)]
mul_inputs = list(zip(values, values[1:] + values[:1]))
rows = [
    paired('mul', lambda pair: f0.mul(*pair), lambda pair: f1.mul(*pair), mul_inputs, 8),
    paired('frob1', lambda value: f0.frob(value, 1), lambda value: f1.frob(value, 1), values, 8),
    paired('from_coords', f0.fromCoords, f1.fromCoords,
           [rng.getrandbits(131) for _ in range(48)], 8),
    paired('to_coords', f0.toCoords, f1.toCoords, values, 8),
]
g0, g1 = OldRunnerField(131), NewRunnerField(131)
c0, c1 = old_curves.Curve(g0), new_curves.Curve(g1)
xs = [g0.fromCoords(rng.getrandbits(131)) for _ in range(24)]
points = [p for p in (c0.pointFromX(x) for x in xs) if p is not None]
assert len(points) >= 5
rows.append(paired('point_from_x', c0.pointFromX, c1.pointFromX, xs, 2))
rows.append(paired('point_dbl', c0.dbl, c1.dbl, points, 2))
print(json.dumps(rows, indent=2))
