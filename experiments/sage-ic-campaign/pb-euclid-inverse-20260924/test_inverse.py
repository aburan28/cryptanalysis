"""Exact polynomial-basis inverse and containing curve-operation checks."""

import importlib.util
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
import curves


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


for variant in ('local', 'runner'):
    old = load('old_' + variant, HERE / ('baseline/field-' + variant + '.py'))
    new = load('new_' + variant, HERE / ('source/field-' + variant + '.py'))
    rng = random.Random(20260924)
    for degree in (2, 3, 4, 5, 6, 7, 8, 11, 13, 15, 53):
        poly, _ = curves.findIrreduciblePoly(degree)
        previous, candidate = old.Pb(degree, poly), new.Pb(degree, poly)
        assert previous.inv(0) == candidate.inv(0) == 0
        values = list(range(1, 1 << degree)) if degree <= 8 else \
            [rng.randrange(1, 1 << degree) for _ in range(100)]
        for a in values:
            expected = previous.inv(a)
            actual = candidate.inv(a)
            assert actual == expected and candidate.mul(a, actual) == 1
            assert candidate.inv(a ^ poly) == expected
        if degree in (5, 11, 15):
            old_curve, new_curve = curves.CurvePb(previous), curves.CurvePb(candidate)
            points = []
            while len(points) < 6:
                point = old_curve.pointFromX(rng.randrange(1, 1 << degree))
                if point is not None:
                    points.append(point)
            for left, right in zip(points, points[1:]):
                assert old_curve.add(left, right) == new_curve.add(left, right)
                assert old_curve.dbl(left) == new_curve.dbl(left)
                for scalar in (1, 3, 7, 127, 2**32 + 1):
                    assert old_curve.mul(left, scalar) == new_curve.mul(left, scalar)
print('local and runner polynomial-basis Euclid inverse checks passed')
