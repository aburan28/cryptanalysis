"""Measure the actual audit curve's point-recovery path, solver excluded."""

import importlib.util
import json
import random
import statistics
import time
from pathlib import Path

import indexcalc_e2e as e


here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('original_field', here / 'baseline/field.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


class OriginalFrobeniusField(e.AuditField):
    def frob(self, a, k):
        self.ledger.counts['field.frob'] += 1
        return original.Onb.frob(self, a, k)


old_ledger, new_ledger = e.Ledger(), e.Ledger()
old_field = OriginalFrobeniusField(131, old_ledger)
new_field = e.AuditField(131, new_ledger)
old_curve = e.AuditCurve(old_field, old_ledger)
new_curve = e.AuditCurve(new_field, new_ledger)
rng = random.Random(20260924)
xs = [old_field.fromCoords(rng.getrandbits(131)) for _ in range(48)]
assert [old_curve.pointFromX(x) for x in xs] == [new_curve.pointFromX(x) for x in xs]


def measure(curve):
    start = time.perf_counter_ns()
    results = [curve.pointFromX(x) for x in xs]
    return time.perf_counter_ns() - start, results


pairs = []
for i in range(7):
    first, second = ((old_curve, new_curve) if i % 2 == 0 else (new_curve, old_curve))
    t0, r0 = measure(first)
    t1, r1 = measure(second)
    assert r0 == r1
    pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
old_ns = statistics.median(pair[0] for pair in pairs)
new_ns = statistics.median(pair[1] for pair in pairs)
print(json.dumps({'case': 'AuditCurve.pointFromX', 'degree': 131,
                  'inputs': len(xs), 'rounds': len(pairs),
                  'successful_points': sum(old_curve.pointFromX(x) is not None for x in xs),
                  'old_ns': old_ns, 'new_ns': new_ns,
                  'speedup': old_ns / new_ns,
                  'pairs': pairs}, indent=2))
