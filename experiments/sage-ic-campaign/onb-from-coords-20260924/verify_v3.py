"""Compare coordinate packing against the frozen original."""

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


old = load(here / 'baseline-v3/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
rng = random.Random(20260927)
checked = 0
for m in (5, 9, 14, 18, 20, 23, 29, 33, 48, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = list(range(1 << m)) if m == 5 else \
        [rng.getrandbits(m) for _ in range(4096 if m == 9 else 512 if m == 131 else 128)]
    values += [rng.getrandbits(m + 17) for _ in range(128)]
    values += [-1, -17, 0, 1 << (m + 5), (1 << m) - 1]
    for a in values:
        assert f0.fromCoords(a) == f1.fromCoords(a), (m, a)
        checked += 1
print('verified original coordinate packing outputs:', checked)
