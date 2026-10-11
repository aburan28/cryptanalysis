"""Check windowed ONB multiplication against the frozen original."""

import importlib.util
import random
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
rng = random.Random(20260925)
count = 0
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    if m == 5:
        pairs = [(f0.fromCoords(a), f0.fromCoords(b))
                 for a in range(1 << m) for b in range(1 << m)]
    else:
        pairs = [(f0.fromCoords(rng.getrandbits(m)),
                  f0.fromCoords(rng.getrandbits(m)))
                 for _ in range(1024 if m == 9 else 256)]
    pairs += [(rng.getrandbits(f0.n), rng.getrandbits(f0.n))
              for _ in range(512 if m == 131 else 128)]
    pairs += [(1 << (f0.n + 2), 1), (f0.allOnes, 1 << (f0.n + 3)),
              (-1, 7), (f0.one(), 0), (0, f0.one())]
    for a, b in pairs:
        expected = f0.mul(a, b)
        actual = f1.mul(a, b)
        assert actual == expected, (m, a, b, expected, actual)
        count += 1
print('verified original multiplication outputs:', count)
