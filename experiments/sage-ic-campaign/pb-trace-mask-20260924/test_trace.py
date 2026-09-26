"""Exact trace-mask and point-recovery checks for both curve copies."""

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
    field = load('field_' + variant, source_dir / 'field.py')
    old = load('old_' + variant, HERE / ('baseline/curves-' + variant + '.py'))
    new = load('new_' + variant, HERE / ('source/curves-' + variant + '.py'))
    assert (source_dir / 'curves.py').read_bytes() == (
        HERE / ('source/curves-' + variant + '.py')).read_bytes()
    rng = random.Random(2026092900 + (variant == 'runner'))
    for degree in range(2, 9):
        poly, _ = old.findIrreduciblePoly(degree)
        incumbent = old.CurvePb(field.Pb(degree, poly))
        candidate = new.CurvePb(field.Pb(degree, poly))
        for value in range(1 << (degree + 1)):
            assert incumbent.trace(value) == candidate.trace(value)
        if degree & 1:
            for x in range(1, 1 << degree):
                assert incumbent.pointFromX(x) == candidate.pointFromX(x)
    for degree in (11, 15, 53, 131):
        poly, _ = old.findIrreduciblePoly(degree)
        incumbent = old.CurvePb(field.Pb(degree, poly))
        candidate = new.CurvePb(field.Pb(degree, poly))
        for _ in range(256):
            value = rng.getrandbits(degree)
            assert incumbent.trace(value) == candidate.trace(value)
        for _ in range(64):
            x = rng.randrange(1, 1 << degree)
            expected = incumbent.pointFromX(x)
            actual = candidate.pointFromX(x)
            assert expected == actual
            assert candidate.onCurve(actual)
print('local and runner polynomial-basis trace-mask checks passed')
