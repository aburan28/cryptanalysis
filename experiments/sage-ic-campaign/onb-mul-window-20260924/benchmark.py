"""Paired ONB multiplication benchmark on fixed canonical input pairs."""

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


def measure(f, pairs, repeat):
    checksum = 0
    start = time.perf_counter_ns()
    for _ in range(repeat):
        for a, b in pairs:
            checksum ^= f.mul(a, b)
    return time.perf_counter_ns() - start, checksum


parser = argparse.ArgumentParser()
parser.add_argument('--incumbent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
args = parser.parse_args()
old = load(args.incumbent, 'old_field')
new = load(args.candidate, 'new_field')
rng = random.Random(20260925)
rows = []
for m, pattern in ((5, 'random'), (9, 'random'), (131, 'random'),
                   (131, 'sparse'), (131, 'dense')):
    f0, f1 = old.Onb(m), new.Onb(m)
    pairs = []
    for _ in range(64):
        a = f0.fromCoords(rng.getrandbits(m))
        if pattern == 'sparse':
            b = f0.fromCoords(1 << rng.randrange(m))
        elif pattern == 'dense':
            b = f0.fromCoords(((1 << m) - 1) ^ (1 << rng.randrange(m)))
        else:
            b = f0.fromCoords(rng.getrandbits(m))
        pairs.append((a, b))
    assert [f0.mul(a, b) for a, b in pairs] == [f1.mul(a, b) for a, b in pairs]
    timings = []
    for i in range(9):
        first, second = ((f0, f1) if i % 2 == 0 else (f1, f0))
        t0, h0 = measure(first, pairs, 8)
        t1, h1 = measure(second, pairs, 8)
        assert h0 == h1
        timings.append((t0, t1) if i % 2 == 0 else (t1, t0))
    old_ns = statistics.median(pair[0] for pair in timings)
    new_ns = statistics.median(pair[1] for pair in timings)
    rows.append({'m': m, 'pattern': pattern, 'pairs': 64,
                 'calls_per_side': 64 * 8 * 9,
                 'old_ns': old_ns, 'new_ns': new_ns,
                 'speedup': old_ns / new_ns})
print(json.dumps(rows, indent=2))
