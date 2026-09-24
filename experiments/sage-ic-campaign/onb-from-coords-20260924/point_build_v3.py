"""Measure sparse coordinate packing within point recovery."""

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


old = load(here / 'baseline-v3/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
sys.modules['field'] = new
curves = load(root / 'ecc2k130/codegen/curves.py', 'curve_module')


class AuditArithmetic:
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


class OldField(AuditArithmetic, old.Onb):
    pass


class NewField(AuditArithmetic, new.Onb):
    pass


f0, f1 = OldField(131), NewField(131)
c0, c1 = curves.Curve(f0), curves.Curve(f1)
rng = random.Random(20260927)
coords = []
for _ in range(64):
    i, j = rng.sample(range(131), 2)
    coords.append((1 << i) | (1 << j))
expected = [c0.pointFromX(f0.fromCoords(a)) for a in coords]
assert expected == [c1.pointFromX(f1.fromCoords(a)) for a in coords]


def measure(curve, field):
    start = time.perf_counter_ns()
    output = None
    for _ in range(32):
        output = [curve.pointFromX(field.fromCoords(a)) for a in coords]
    return time.perf_counter_ns() - start, output


pairs = []
for i in range(11):
    first_curve, first_field, second_curve, second_field = \
        ((c0, f0, c1, f1) if i % 2 == 0 else (c1, f1, c0, f0))
    t0, r0 = measure(first_curve, first_field)
    t1, r1 = measure(second_curve, second_field)
    assert r0 == r1 == expected
    pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
print(json.dumps({'case': 'Curve.pointFromX(Onb.fromCoords)', 'm': 131,
                  'inputs': len(coords), 'successful_points': sum(p is not None for p in expected),
                  'input_sha256': hashlib.sha256(json.dumps(coords).encode()).hexdigest(),
                  'rounds': len(pairs), 'repeat': 32,
                  'paired_speedup': statistics.median(a / b for a, b in pairs),
                  'pairs': pairs}, indent=2))
