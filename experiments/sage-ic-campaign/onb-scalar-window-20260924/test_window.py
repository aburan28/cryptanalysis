"""Exact local and tracked-runner ONB scalar-window checks."""

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
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


for variant in ('local', 'runner'):
    old = load('old_' + variant, HERE / ('baseline/curves-' + variant + '.py'))
    new = load('new_' + variant, HERE / ('source/curves-' + variant + '.py'))
    rng = random.Random(20260924)
    for degree in (3, 5, 9, 53, 131):
        onb = field.Onb(degree)
        baseline, candidate = old.Curve(onb), new.Curve(onb)
        points = [None, (0, onb.one())]
        if degree <= 9:
            for x in range(1 << degree):
                p = baseline.pointFromX(onb.fromCoords(x))
                if p is not None:
                    points.append(p)
        else:
            while len(points) < 5:
                p = baseline.pointFromX(onb.randomElement(rng))
                if p is not None:
                    points.append(p)
        scalars = list(range(0, 65)) if degree <= 9 else list(range(0, 9))
        scalars += [2**32 - 1, 2**32, 2**32 + 1,
                    2**64 - 1, 2**64, 2**64 + 1, 2**131 - 1]
        for point in points:
            for scalar in scalars:
                expected = baseline.mul(point, scalar)
                actual = candidate.mul(point, scalar)
                assert actual == expected, (variant, degree, point, scalar)
                assert candidate.onCurve(actual)
                assert candidate.mul(point, -scalar) == candidate.neg(expected)
print('local and runner ONB signed-window scalar checks passed')
