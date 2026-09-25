"""Compare coordinate extraction against the frozen original."""

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


old = load(here / 'baseline-v2/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
rng = random.Random(20260926)
checked = 0
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    values = list(range(1 << f0.n)) if m == 5 else \
        [rng.getrandbits(f0.n) for _ in range(4096 if m == 9 else 512)]
    values += [f0.fromCoords(rng.getrandbits(m)) for _ in range(128)]
    values += [-1, -17, 0, f0.allOnes, 1 << (f0.n + 5)]
    for u in values:
        assert f0.toCoords(u) == f1.toCoords(u), (m, u)
        checked += 1
print('verified original coordinate outputs:', checked)
