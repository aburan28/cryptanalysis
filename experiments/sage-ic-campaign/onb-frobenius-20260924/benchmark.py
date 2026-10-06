"""Paired local ONB field benchmark, independent of Sage installation."""

import argparse
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


def measure(fn, values, repeat):
    checksum = 0
    start = time.perf_counter_ns()
    for _ in range(repeat):
        for value in values:
            result = fn(value)
            checksum ^= result[0] ^ result[1] if isinstance(result, tuple) else result
    return time.perf_counter_ns() - start, checksum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--incumbent', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=9)
    parser.add_argument('--repeat', type=int, default=16)
    args = parser.parse_args()
    rng = random.Random(20260924)
    old = load(args.incumbent, 'incumbent_field')
    new = load(args.candidate, 'candidate_field')
    sys.modules['field'] = new
    curves = load(args.candidate.parents[0] / 'curves.py', 'candidate_curves')
    rows = []
    for m in (5, 9, 131):
        f0, f1 = old.Onb(m), new.Onb(m)
        values = [f0.fromCoords(rng.getrandbits(m)) for _ in range(64)]
        for k in (1, 2):
            assert [f0.frob(a, k) for a in values] == [f1.frob(a, k) for a in values]
            pairs = []
            for i in range(args.rounds):
                first, second = ((f0, f1) if i % 2 == 0 else (f1, f0))
                t0, h0 = measure(lambda a: first.frob(a, k), values, args.repeat)
                t1, h1 = measure(lambda a: second.frob(a, k), values, args.repeat)
                assert h0 == h1
                pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
            old_ns = statistics.median(p[0] for p in pairs)
            new_ns = statistics.median(p[1] for p in pairs)
            rows.append({'case': 'frob', 'm': m, 'k': k,
                         'old_ns': old_ns, 'new_ns': new_ns,
                         'speedup': old_ns / new_ns,
                         'calls_per_side': len(values) * args.repeat * args.rounds})
        if m == 131:
            c0, c1 = curves.Curve(f0), curves.Curve(f1)
            assert [c0.halfTrace(a) for a in values] == [c1.halfTrace(a) for a in values]
            points = [(a, f0.frob(a, 1)) for a in values]
            assert [c0.frob(p) for p in points] == [c1.frob(p) for p in points]
            for label, fn0, fn1 in (
                ('halftrace', c0.halfTrace, c1.halfTrace),
                ('point_frob', c0.frob, c1.frob),
            ):
                stage_values = points if label == 'point_frob' else values
                pairs = []
                for i in range(args.rounds):
                    first, second = ((fn0, fn1) if i % 2 == 0 else (fn1, fn0))
                    t0, h0 = measure(first, stage_values, 1)
                    t1, h1 = measure(second, stage_values, 1)
                    assert h0 == h1
                    pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
                old_ns = statistics.median(p[0] for p in pairs)
                new_ns = statistics.median(p[1] for p in pairs)
                rows.append({'case': label, 'm': m,
                             'old_ns': old_ns, 'new_ns': new_ns,
                             'speedup': old_ns / new_ns,
                             'calls_per_side': len(stage_values) * args.rounds})
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
