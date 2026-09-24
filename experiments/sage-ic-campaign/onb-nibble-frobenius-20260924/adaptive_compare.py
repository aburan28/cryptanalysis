"""Paired parent/adaptive Frobenius and point-recovery benchmark."""

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
curves = load(root / 'ecc2k130/codegen/curves.py', 'curves')


class RunnerInverse:
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
        return new.popcount(self.toCoords(value)) & 1


class OldField(RunnerInverse, old.Onb):
    pass


class NewField(RunnerInverse, new.Onb):
    pass


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    result = None
    for _ in range(repeat):
        result = [fn(x) for x in values]
    return time.perf_counter_ns() - start, result


def paired(case, m, fn0, fn1, values, repeat):
    expected = [fn0(x) for x in values]
    assert expected == [fn1(x) for x in values]
    pairs = []
    for i in range(9):
        a, b = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        ta, ra = timed(a, values, repeat)
        tb, rb = timed(b, values, repeat)
        assert ra == rb == expected
        pairs.append((ta, tb) if i % 2 == 0 else (tb, ta))
    return {'case': case, 'degree': m, 'inputs': len(values), 'repeat': repeat,
            'pairs': pairs, 'speed_fraction_of_parent': statistics.median(a / b for a, b in pairs)}


rng = random.Random(20260924)
rows = []
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = [f0.fromCoords(rng.getrandbits(m)) for _ in range(64)]
    for k in (1, 2):
        rows.append(paired('frob' + str(k), m, lambda a: f0.frob(a, k),
                           lambda a: f1.frob(a, k), values, 16))
f0, f1 = OldField(131), NewField(131)
c0, c1 = curves.Curve(f0), curves.Curve(f1)
xs = [f0.fromCoords(rng.getrandbits(131)) for _ in range(24)]
rows.append(paired('point_from_x', 131, c0.pointFromX, c1.pointFromX, xs, 2))
print(json.dumps(rows, indent=2))
