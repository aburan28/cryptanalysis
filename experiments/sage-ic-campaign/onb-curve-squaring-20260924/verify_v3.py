"""Check Frobenius squares and curve points against the frozen original."""

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


old = load(here / 'baseline-v3/field.py', 'old_field')
new = load(root / 'ecc2k130/codegen/field.py', 'new_field')
sys.modules['field'] = old
old_curves = load(here / 'baseline/curves.py', 'old_curves')
sys.modules['field'] = new
new_curves = load(root / 'ecc2k130/codegen/curves.py', 'new_curves')
rng = random.Random(20260928)
checked = 0


class EuclidInverse:
    def inv(self, value):
        if not value:
            raise ZeroDivisionError()
        a, b, u, v = value, self.allOnes, 1, 0
        while a != 1:
            if not a:
                raise ValueError('nonunit in the ONB ring')
            shift = a.bit_length() - b.bit_length()
            if shift < 0:
                a, b, u, v = b, a, v, u
                shift = -shift
            a ^= b << shift
            u ^= v << shift
        while u.bit_length() >= self.allOnes.bit_length():
            u ^= self.allOnes << (u.bit_length() - self.allOnes.bit_length())
        return self.normalize(u)

    def trace(self, value):
        return old.popcount(self.toCoords(value)) & 1


class OldField(EuclidInverse, old.Onb):
    pass


class NewField(EuclidInverse, new.Onb):
    pass


for m in (5, 9, 131):
    f0, f1 = OldField(m), NewField(m)
    c0, c1 = old_curves.Curve(f0), new_curves.Curve(f1)
    for _ in range(256):
        a = rng.getrandbits(f0.n)
        assert f0.sqr(a) == f1.sqr(a)
        checked += 1
    points = []
    for _ in range(32):
        x = f0.fromCoords(rng.getrandbits(m))
        p0, p1 = c0.pointFromX(x), c1.pointFromX(x)
        assert p0 == p1
        assert c0.onCurve(p0) == c1.onCurve(p1)
        if p0 is not None:
            points.append(p0)
        checked += 2
    assert c0.onCurve(None) == c1.onCurve(None)
    assert c0.add(None, None) == c1.add(None, None)
    for p in points[:8]:
        assert c0.dbl(p) == c1.dbl(p)
        assert c0.add(p, p) == c1.add(p, p)
        assert c0.add(p, c0.neg(p)) == c1.add(p, c1.neg(p))
        assert c0.mul(p, 17) == c1.mul(p, 17)
        checked += 4
    for p, q in zip(points[:8], points[1:9]):
        assert c0.add(p, q) == c1.add(p, q)
        checked += 1
print('verified original square and curve outputs:', checked)
