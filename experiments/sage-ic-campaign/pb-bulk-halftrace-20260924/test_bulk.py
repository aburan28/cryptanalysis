"""Exact half-trace and IC factor-base checks for explicit bulk preparation."""

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
    curves = load('curves_' + variant, source_dir / 'curves.py')
    rng = random.Random(2026100100 + (variant == 'runner'))
    for degree in (3, 5, 7, 11, 15, 53, 131):
        poly, _ = curves.findIrreduciblePoly(degree)
        incumbent = curves.CurvePb(field.Pb(degree, poly))
        candidate = curves.CurvePb(field.Pb(degree, poly))
        candidate.prepareHalfTrace()
        original = candidate._halfTraceImages
        candidate.prepareHalfTrace()
        assert candidate._halfTraceImages is original
        for _ in range(128):
            value = rng.getrandbits(degree)
            assert incumbent.halfTrace(value) == candidate.halfTrace(value)
        for _ in range(16):
            x = rng.randrange(1, 1 << degree)
            assert incumbent.pointFromX(x) == candidate.pointFromX(x)

sys.path.insert(0, str(ROOT / 'ecc2k130/runner/codegen'))
import curves
import indexcalc
for degree, weight in ((11, 3), (13, 3)):
    onb = curves.NormalView(degree)
    old = curves.CurvePb(onb.pb)
    new = curves.CurvePb(onb.pb)
    assert indexcalc.factorBase(onb, old, weight) == indexcalc.factorBase(
        onb, new, weight, True)
    assert old._halfTraceImages is None and new._halfTraceImages is not None
try:
    indexcalc.factorBase(curves.NormalView(11), curves.Curve(field.Onb(11)),
                         2, True)
except ValueError as error:
    assert 'polynomial-basis' in str(error)
else:
    raise AssertionError('bulk preparation accepted an ONB curve')
print('local and runner explicit bulk half-trace checks passed')
