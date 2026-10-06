"""Exact polynomial-basis Koblitz scalar and Frobenius identity checks."""

import importlib.util
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
import field


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


for variant in ('local', 'runner'):
    old = load('old_' + variant, HERE / ('baseline/curves-' + variant + '.py'))
    new = load('new_' + variant, HERE / ('source/curves-' + variant + '.py'))
    for degree in (2, 3, 4, 5, 6, 11, 13, 15):
        poly, _ = old.findIrreduciblePoly(degree)
        pb = field.Pb(degree, poly)
        baseline, candidate = old.CurvePb(pb), new.CurvePb(pb)
        points = [None, (0, 1)]
        if degree <= 6:
            all_points = [(x, y) for x in range(1 << degree)
                          for y in range(1 << degree)
                          if baseline.onCurve((x, y))]
            points += all_points if degree <= 4 else all_points[:12]
        else:
            rng = random.Random(20260924 + degree)
            while len(points) < 8:
                point = baseline.pointFromX(rng.randrange(1, 1 << degree))
                if point is not None:
                    points.append(point)
        scalars = list(range(33)) if degree <= 6 else list(range(9))
        scalars += [127, 128, 255, 256, 2**16 - 1, 2**32 + 1,
                    2**64 - 1, 2**131 - 1]
        for point in points:
            if point is not None:
                tau2 = candidate.frob(candidate.frob(point))
                tau = candidate.frob(point)
                assert candidate.add(candidate.add(tau2, tau),
                                     candidate.dbl(point)) is None
            for scalar in scalars:
                expected = baseline.mul(point, scalar)
                actual = candidate.mul(point, scalar)
                assert actual == expected, (variant, degree, point, scalar)
                assert candidate.onCurve(actual)
                assert candidate.mul(point, -scalar) == candidate.neg(expected)
print('local and runner polynomial-basis tau-adic checks passed')
