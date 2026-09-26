"""Alternating paired trace and point-recovery stage benchmark."""

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


def timed(fn, values, repeat):
    start = time.perf_counter_ns()
    output = None
    for _ in range(repeat):
        output = [fn(value) for value in values]
    return time.perf_counter_ns() - start, output


def paired(fn0, fn1, values, repeat):
    expected = [fn0(value) for value in values]
    assert expected == [fn1(value) for value in values]
    pairs = []
    for i in range(9):
        first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        ta, ra = timed(first, values, repeat)
        tb, rb = timed(second, values, repeat)
        assert ra == rb == expected
        pairs.append((ta, tb) if i % 2 == 0 else (tb, ta))
    return {'pairs': pairs, 'paired_speedup': statistics.median(a / b for a, b in pairs),
            'old_ns': statistics.median(a for a, _ in pairs),
            'new_ns': statistics.median(b for _, b in pairs),
            'inputs': len(values), 'rounds': 9, 'repeat': repeat,
            'input_sha256': hashlib.sha256(json.dumps(values).encode()).hexdigest()}


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


old = load(here / 'baseline/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
sys.modules['field'] = old
old_curves = load(root / 'ecc2k130/codegen/curves.py', 'old_curves')
sys.modules['field'] = new
new_curves = load(root / 'ecc2k130/codegen/curves.py', 'new_curves')
rng = random.Random(20260924)
rows = []
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = [f0.fromCoords(rng.getrandbits(m)) for _ in range(64)]
    result = paired(f0.trace, f1.trace, values, 8)
    result.update(case='trace', degree=m)
    rows.append(result)


class OldField(EuclidInverse, old.Onb):
    pass


class NewField(EuclidInverse, new.Onb):
    pass


f0, f1 = OldField(131), NewField(131)
c0, c1 = old_curves.Curve(f0), new_curves.Curve(f1)
by_outcome = {False: [], True: []}
while min(len(group) for group in by_outcome.values()) < 24:
    x = f0.fromCoords(rng.getrandbits(131))
    valid = c0.pointFromX(x) is not None
    if len(by_outcome[valid]) < 24:
        by_outcome[valid].append(x)
for valid, values in by_outcome.items():
    result = paired(c0.pointFromX, c1.pointFromX, values, 2)
    result.update(case='point_from_x_valid' if valid else 'point_from_x_invalid', degree=131)
    rows.append(result)
print(json.dumps(rows, indent=2))
