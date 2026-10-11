"""Compare the byte table against the frozen original, including odd inputs."""

import importlib.util
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load(HERE / 'baseline/field.py', 'old_field')
new = load(ROOT / 'ecc2k130/codegen/field.py', 'new_field')
rng = random.Random(20260924)
checked = 0
for m in (5, 9, 131):
    f0, f1 = old.Onb(m), new.Onb(m)
    if m == 5:
        inputs = list(range(1 << f0.n))
    else:
        inputs = [rng.getrandbits(f0.n) for _ in range(4096 if m == 9 else 512)]
    inputs += [0, f0.allOnes, -1, -17, 1 << (f0.n + 5)]
    for a in inputs:
        for k in (-m, -1, 0, 1, 2, m, m + 1, 2 * m + 3):
            expected = f0.frob(a, k)
            actual = f1.frob(a, k)
            assert actual == expected, (m, a, k, expected, actual)
            checked += 1
    for _ in range(24):
        a = f0.fromCoords(rng.getrandbits(m))
        assert f1.frob(a, 1) == f0.mul(a, a)
        assert f1.frob(a, m) == a
    assert set(f1.frobPositions).issubset({2, 4})
    assert len(f1.frobPositions) <= 2
print('verified original Frobenius outputs:', checked)
