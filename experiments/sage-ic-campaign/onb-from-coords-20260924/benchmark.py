"""Paired ONB coordinate packing benchmark."""

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
    for _ in range(16):
        for a in values:
            checksum ^= fn(a)
    return time.perf_counter_ns() - start, checksum


parser = argparse.ArgumentParser()
parser.add_argument('--incumbent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
args = parser.parse_args()
old = load(args.incumbent, 'old_field')
new = load(args.candidate, 'new_field')
rng = random.Random(20260927)
rows = []
for m, pattern in ((5, 'random'), (9, 'random'), (131, 'random'),
                   (131, 'sparse_one'), (131, 'sparse_two'), (131, 'dense')):
    f0, f1 = old.Onb(m), new.Onb(m)
    if pattern == 'sparse_one':
        values = [1 << rng.randrange(m) for _ in range(64)]
    elif pattern == 'sparse_two':
        values = [(1 << i) | (1 << j) for i, j in
                  ((rng.randrange(m), rng.randrange(m)) for _ in range(64))]
    elif pattern == 'dense':
        values = [((1 << m) - 1) ^ (1 << rng.randrange(m)) for _ in range(64)]
    else:
        values = [rng.getrandbits(m) for _ in range(64)]
    assert [f0.fromCoords(a) for a in values] == [f1.fromCoords(a) for a in values]
    pairs = []
    for i in range(9):
        first, second = ((f0, f1) if i % 2 == 0 else (f1, f0))
        t0, h0 = measure(first.fromCoords, values)
        t1, h1 = measure(second.fromCoords, values)
        assert h0 == h1
        pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
    old_ns = statistics.median(pair[0] for pair in pairs)
    new_ns = statistics.median(pair[1] for pair in pairs)
    rows.append({'m': m, 'pattern': pattern, 'samples': 64,
                 'calls_per_side': 64 * 16 * 9,
                 'old_ns': old_ns, 'new_ns': new_ns,
                 'speedup': old_ns / new_ns})
print(json.dumps(rows, indent=2))
