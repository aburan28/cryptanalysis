"""Compare parity trace and containing curve outputs with frozen source."""

import importlib.util
import random
import sys
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
sys.modules['field'] = old
old_curves = load(root / 'ecc2k130/codegen/curves.py', 'old_curves')
sys.modules['field'] = new
new_curves = load(root / 'ecc2k130/codegen/curves.py', 'new_curves')
rng = random.Random(20260924)
checked = 0
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    inputs = list(range(1 << f0.n)) if m == 5 else \
        [f0.fromCoords(rng.getrandbits(m)) for _ in range(1024)]
    inputs += [0, -1, -2, 1 << f0.n, (1 << (f0.n + 5)) | 1]
    inputs += [rng.getrandbits(f0.n + 9) for _ in range(128)]
    for value in inputs:
        assert f0.trace(value) == f1.trace(value), (m, value)
        if value == f1.fromCoords(f1.toCoords(value)):
            assert f1.trace(value) == (new.popcount(f1.toCoords(value)) & 1)
        checked += 1
    c0, c1 = old_curves.Curve(f0), new_curves.Curve(f1)
    for _ in range(48):
        x = f0.fromCoords(rng.getrandbits(m))
        assert c0.pointFromX(x) == c1.pointFromX(x)
        checked += 1
print('exact trace and point outputs:', checked)
