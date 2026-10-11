"""Paired Koblitz point operations with only the ONB multiplication changed."""

import hashlib
import importlib.util
import json
import random
import statistics
import sys
import time
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load(here / 'baseline/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
sys.modules['field'] = new
curves = load(root / 'ecc2k130/codegen/curves.py', 'curve_module')


class EuclidInverse:
    # Identical inverse and trace implementation on both compared fields.
    def inv(self, value):
        if not value:
            raise ZeroDivisionError()
        a, b, u, v = value, self.allOnes, 1, 0
        while a != 1:
            if not a:
                raise ValueError('nonunit in the ONB ring')
            shift = a.bit_length() - b.bit_length()
            if shift < 0:
                a, b, u, v = b, a, v, u
                shift = -shift
            a ^= b << shift
            u ^= v << shift
        while u.bit_length() >= self.allOnes.bit_length():
            u ^= self.allOnes << (u.bit_length() - self.allOnes.bit_length())
        return self.normalize(u)

    def trace(self, value):
        return self.toCoords(value).bit_count() & 1


class OldField(EuclidInverse, old.Onb):
    pass


class NewField(EuclidInverse, new.Onb):
    pass


f0, f1 = OldField(131), NewField(131)
c0, c1 = curves.Curve(f0), curves.Curve(f1)
rng = random.Random(20260925)
xs = [f0.fromCoords(rng.getrandbits(131)) for _ in range(48)]
recovered = [c0.pointFromX(x) for x in xs]
assert recovered == [c1.pointFromX(x) for x in xs]
points = [p for p in recovered if p is not None]
assert len(points) >= 12
pairs = list(zip(points, points[1:]))
input_hash = hashlib.sha256(json.dumps(xs).encode()).hexdigest()


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    outputs = None
    for _ in range(repeat):
        outputs = [fn(value) for value in values]
    return time.perf_counter_ns() - start, outputs


rows = []
cases = (
    ('pointFromX', xs, c0.pointFromX, c1.pointFromX, 16),
    ('add', pairs, lambda pair: c0.add(*pair), lambda pair: c1.add(*pair), 16),
    ('dbl', points, c0.dbl, c1.dbl, 16),
    ('scalar_mul_17', points[:8], lambda point: c0.mul(point, 17),
     lambda point: c1.mul(point, 17), 2),
    ('frob_control', points, c0.frob, c1.frob, 128),
)
for label, values, fn0, fn1, repeat in cases:
    expected = [fn0(value) for value in values]
    assert expected == [fn1(value) for value in values], label
    measurements = []
    for i in range(11):
        first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        t0, r0 = timed(first, values, repeat)
        t1, r1 = timed(second, values, repeat)
        assert r0 == r1 == expected, label
        measurements.append((t0, t1) if i % 2 == 0 else (t1, t0))
    old_ns = statistics.median(pair[0] for pair in measurements)
    new_ns = statistics.median(pair[1] for pair in measurements)
    rows.append({'case': label, 'm': 131, 'inputs': len(values),
                 'repeat': repeat, 'rounds': 11, 'input_sha256': input_hash,
                 'old_ns': old_ns, 'new_ns': new_ns,
                 'speedup': old_ns / new_ns,
                 'paired_speedup': statistics.median(a / b for a, b in measurements),
                 'pairs': measurements})
print(json.dumps(rows, indent=2))
