"""Compare fixed-window Frobenius tables before changing tracked source."""

import importlib.util
import json
import random
import statistics
import time
from pathlib import Path


here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('baseline_field', here / 'baseline/field.py')
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)
f = field.Onb(131)
rng = random.Random(20260924)
values = [f.fromCoords(rng.getrandbits(131)) for _ in range(64)]


def build(e, width):
    positions = tuple(1 << (i * e % f.n) for i in range(f.n))
    padded = positions + (0,) * (-f.n % width)
    tables = []
    for offset in range(0, len(padded), width):
        table = [0] * (1 << width)
        for digit in range(1, 1 << width):
            bit = digit & -digit
            table[digit] = table[digit ^ bit] | padded[offset + bit.bit_length() - 1]
        tables.append(tuple(table))
    return tuple(tables)


def transform(value, tables, width):
    bits = value & f.allOnes
    mask = (1 << width) - 1
    result = 0
    for table in tables:
        result |= table[bits & mask]
        bits >>= width
    return f.normalize(result)


def timed(fn):
    start = time.perf_counter_ns()
    result = None
    for _ in range(16):
        result = [fn(x) for x in values]
    return time.perf_counter_ns() - start, result


rows = []
for k in (1, 2):
    e = pow(2, k, f.n)
    expected = [f.frob(x, k) for x in values]
    for width in (4, 5, 6, 7, 8):
        build_times = []
        for _ in range(21):
            start = time.perf_counter_ns()
            tables = build(e, width)
            build_times.append(time.perf_counter_ns() - start)
        fn = lambda x: transform(x, tables, width)
        assert [fn(x) for x in values] == expected
        pairs = []
        for i in range(7):
            a, b = ((lambda x: f.frob(x, k), fn) if i % 2 == 0 else
                    (fn, lambda x: f.frob(x, k)))
            ta, ra = timed(a)
            tb, rb = timed(b)
            assert ra == rb == expected
            pairs.append((ta, tb) if i % 2 == 0 else (tb, ta))
        rows.append({'k': k, 'width': width, 'chunks': len(tables),
                     'table_entries': sum(len(t) for t in tables),
                     'build_median_ns': statistics.median(build_times),
                     'warm_speed_fraction_of_parent': statistics.median(a / b for a, b in pairs),
                     'pairs': pairs})
print(json.dumps(rows, indent=2))
