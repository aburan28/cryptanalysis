"""Paired ONB squaring and complete curve-operation benchmark."""

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
import sys
import time
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    output = None
    for _ in range(repeat):
        output = [fn(value) for value in values]
    return time.perf_counter_ns() - start, output


def paired(fn0, fn1, values, rounds, repeat):
    expected = [fn0(value) for value in values]
    assert expected == [fn1(value) for value in values]
    pairs = []
    for i in range(rounds):
        first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        t0, r0 = timed(first, values, repeat)
        t1, r1 = timed(second, values, repeat)
        assert r0 == r1 == expected
        pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
    old_ns = statistics.median(a for a, _ in pairs)
    new_ns = statistics.median(b for _, b in pairs)
    return {'old_ns': old_ns, 'new_ns': new_ns,
            'speedup': old_ns / new_ns,
            'paired_speedup': statistics.median(a / b for a, b in pairs),
            'pairs': pairs, 'rounds': rounds, 'repeat': repeat}


parser = argparse.ArgumentParser()
parser.add_argument('--incumbent-field', type=Path, required=True)
parser.add_argument('--incumbent-curves', type=Path, required=True)
parser.add_argument('--candidate-field', type=Path, required=True)
parser.add_argument('--candidate-curves', type=Path, required=True)
args = parser.parse_args()
old = load(args.incumbent_field, 'old_field')
new = load(args.candidate_field, 'new_field')
sys.modules['field'] = old
old_curves = load(args.incumbent_curves, 'old_curves')
sys.modules['field'] = new
new_curves = load(args.candidate_curves, 'new_curves')
rng = random.Random(20260928)
rows = []
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = [f0.fromCoords(rng.getrandbits(m)) for _ in range(64)]
    row = paired(f0.sqr, f1.sqr, values, 9, 32)
    row.update(case='sqr', m=m, inputs=len(values))
    rows.append(row)


class EuclidInverse:
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
c0, c1 = old_curves.Curve(f0), new_curves.Curve(f1)
xs = [f0.fromCoords(rng.getrandbits(131)) for _ in range(48)]
points = [p for p in (c0.pointFromX(x) for x in xs) if p is not None]
assert len(points) >= 12
assert [c0.pointFromX(x) for x in xs] == [c1.pointFromX(x) for x in xs]
point_pairs = list(zip(points, points[1:]))
input_hash = hashlib.sha256(json.dumps(xs).encode()).hexdigest()
for name, values, fn0, fn1 in (
    ('onCurve', points, c0.onCurve, c1.onCurve),
    ('dbl', points, c0.dbl, c1.dbl),
    ('add', point_pairs, lambda pair: c0.add(*pair), lambda pair: c1.add(*pair)),
    ('pointFromX', xs, c0.pointFromX, c1.pointFromX),
    ('scalar_mul_17', points[:8], lambda p: c0.mul(p, 17), lambda p: c1.mul(p, 17)),
):
    row = paired(fn0, fn1, values, 11, 8)
    row.update(case=name, m=131, inputs=len(values), input_sha256=input_hash)
    rows.append(row)
print(json.dumps(rows, indent=2))
