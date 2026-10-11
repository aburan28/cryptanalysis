"""Paired ONB coordinate extraction and audit-style trace benchmark."""

import argparse
import importlib.util
import json
import random
import statistics
import time
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(fn, values):
    checksum = 0
    start = time.perf_counter_ns()
    for _ in range(32):
        for value in values:
            checksum ^= fn(value)
    return time.perf_counter_ns() - start, checksum


parser = argparse.ArgumentParser()
parser.add_argument('--incumbent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
args = parser.parse_args()
old = load(args.incumbent, 'old_field')
new = load(args.candidate, 'new_field')
rng = random.Random(20260926)
rows = []
for m, pattern in ((5, 'random'), (9, 'random'), (131, 'random'),
                   (131, 'sparse'), (131, 'audit_trace')):
    f0, f1 = old.Onb(m), new.Onb(m)
    if pattern == 'sparse':
        values = [f0.fromCoords(1 << rng.randrange(m)) for _ in range(64)]
    else:
        values = [f0.fromCoords(rng.getrandbits(m)) for _ in range(64)]
    if pattern == 'audit_trace':
        fn0 = lambda u: f0.toCoords(u).bit_count() & 1
        fn1 = lambda u: f1.toCoords(u).bit_count() & 1
    else:
        fn0, fn1 = f0.toCoords, f1.toCoords
    assert [fn0(u) for u in values] == [fn1(u) for u in values]
    pairs = []
    for i in range(9):
        first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
        t0, h0 = measure(first, values)
        t1, h1 = measure(second, values)
        assert h0 == h1
        pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
    old_ns = statistics.median(pair[0] for pair in pairs)
    new_ns = statistics.median(pair[1] for pair in pairs)
    rows.append({'m': m, 'pattern': pattern, 'samples': 64,
                 'calls_per_side': 64 * 32 * 9,
                 'old_ns': old_ns, 'new_ns': new_ns,
                 'speedup': old_ns / new_ns})
print(json.dumps(rows, indent=2))
