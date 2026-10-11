"""Long paired control for the Frobenius method unchanged by this patch."""

import importlib.util
import json
import random
import statistics
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
f0, f1 = old.Onb(131), new.Onb(131)
rng = random.Random(20260925)
values = [f0.fromCoords(rng.getrandbits(131)) for _ in range(64)]
assert [f0.frob(a, 1) for a in values] == [f1.frob(a, 1) for a in values]


def timed(field):
    start = time.perf_counter_ns()
    output = None
    for _ in range(128):
        output = [field.frob(a, 1) for a in values]
    return time.perf_counter_ns() - start, output


pairs = []
for i in range(21):
    first, second = ((f0, f1) if i % 2 == 0 else (f1, f0))
    t0, r0 = timed(first)
    t1, r1 = timed(second)
    assert r0 == r1
    pairs.append((t0, t1) if i % 2 == 0 else (t1, t0))
print(json.dumps({'case': 'unchanged_Onb.frob', 'm': 131,
                  'inputs': len(values), 'rounds': len(pairs), 'repeat': 128,
                  'paired_speedup': statistics.median(a / b for a, b in pairs),
                  'pairs': pairs}, indent=2))
