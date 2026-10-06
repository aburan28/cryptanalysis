"""Reproduce the IC point-recovery path with only tracked field/curve code."""

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


original = load(here / 'baseline/field.py', 'original_field')
candidate = load(root / 'ecc2k130/codegen/field.py', 'candidate_field')
sys.modules['field'] = candidate
curves = load(root / 'ecc2k130/codegen/curves.py', 'curve_module')


class EuclidInverse:
    # Same inverse used by the local IC audit runner for both compared fields.
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


class OldField(EuclidInverse, original.Onb):
    pass


class NewField(EuclidInverse, candidate.Onb):
    pass


old_field, new_field = OldField(131), NewField(131)
old_curve, new_curve = curves.Curve(old_field), curves.Curve(new_field)
rng = random.Random(20260924)
xs = [old_field.fromCoords(rng.getrandbits(131)) for _ in range(48)]
expected = [old_curve.pointFromX(x) for x in xs]
assert expected == [new_curve.pointFromX(x) for x in xs]


def measure(curve):
    start = time.perf_counter_ns()
    result = [curve.pointFromX(x) for x in xs]
    return time.perf_counter_ns() - start, result


pairs = []
for i in range(7):
    first, second = ((old_curve, new_curve) if i % 2 == 0 else (new_curve, old_curve))
    t0, r0 = measure(first)
    t1, r1 = measure(second)
    assert r0 == r1 == expected
    pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
old_ns = statistics.median(pair[0] for pair in pairs)
new_ns = statistics.median(pair[1] for pair in pairs)
input_hash = hashlib.sha256(json.dumps(xs).encode()).hexdigest()
print(json.dumps({'case': 'Curve.pointFromX', 'degree': 131,
                  'input_sha256': input_hash, 'inputs': len(xs),
                  'rounds': len(pairs),
                  'successful_points': sum(p is not None for p in expected),
                  'old_ns': old_ns, 'new_ns': new_ns,
                  'speedup': old_ns / new_ns, 'pairs': pairs}, indent=2))
