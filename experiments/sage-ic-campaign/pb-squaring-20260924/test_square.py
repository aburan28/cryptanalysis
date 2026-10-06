"""Exact checks for the local and tracked runner polynomial-basis square."""

import importlib.util
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


for variant in ('local', 'runner'):
    source_dir = ROOT / 'ecc2k130' / ('codegen' if variant == 'local'
                                      else 'runner/codegen')
    sys.path.insert(0, str(source_dir))
    curves = load('curves_' + variant, source_dir / 'curves.py')
    old = load('old_' + variant, HERE / ('baseline/field-' + variant + '.py'))
    new = load('new_' + variant, HERE / ('source/field-' + variant + '.py'))
    assert (source_dir / 'field.py').read_bytes() == (
        HERE / ('source/field-' + variant + '.py')).read_bytes()
    rng = random.Random(2026092800 + (variant == 'runner'))
    for degree in range(2, 9):
        poly, _ = curves.findIrreduciblePoly(degree)
        incumbent, candidate = old.Pb(degree, poly), new.Pb(degree, poly)
        for value in range(1 << (degree + 1)):
            assert incumbent.sqr(value) == candidate.sqr(value)
    for degree in (11, 15, 53, 131):
        poly, _ = curves.findIrreduciblePoly(degree)
        incumbent, candidate = old.Pb(degree, poly), new.Pb(degree, poly)
        for _ in range(256):
            value = rng.getrandbits(degree)
            assert incumbent.sqr(value) == candidate.sqr(value)
            assert incumbent.sqr(value | (1 << degree)) == candidate.sqr(
                value | (1 << degree))
        old_curve, new_curve = curves.CurvePb(incumbent), curves.CurvePb(candidate)
        point = None
        while point is None:
            point = old_curve.pointFromX(rng.randrange(1, 1 << degree))
        for scalar in (0, 1, 2, 7, (1 << 31) | rng.getrandbits(31)):
            expected = old_curve.mul(point, scalar)
            actual = new_curve.mul(point, scalar)
            assert expected == actual
            assert new_curve.onCurve(actual)
print('local and runner polynomial-basis square checks passed')
