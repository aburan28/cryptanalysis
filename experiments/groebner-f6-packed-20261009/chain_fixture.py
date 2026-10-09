"""Rebuild the frozen planted S3-chain equations for packed-factor replay."""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-20261008'))
from chain_profile import GF2n, Curve, coordinate, equations, profile, s3
from separator import canonical, satisfies, scope_of


def fixture(n, m, ell, seed):
    expected = profile(n, m, ell, seed)
    field = GF2n(n)
    curve = Curve(field, 1)
    rng = random.Random(seed)
    for attempt in range(1, 1001):
        points = [curve.random_factor_base_point(ell, rng) for _ in range(m)]
        partials = [curve.sum(points[:i]) for i in range(2, m + 1)]
        if all(not point.inf for point in partials):
            break
    else:
        raise ValueError('could not reconstruct finite intermediate points')
    assert attempt == expected['fixture_attempt']
    target_x = partials[-1].x
    summands = [coordinate(i * ell, ell) for i in range(m)]
    auxiliaries = [coordinate(m * ell + i * n, n) for i in range(m - 2)]
    factors = [s3(field, 1, summands[0], summands[1], auxiliaries[0])]
    for i in range(1, m - 2):
        factors.append(s3(field, 1, auxiliaries[i - 1], summands[i + 1], auxiliaries[i]))
    factors.append(s3(field, 1, auxiliaries[-1], summands[-1], {0: target_x}))
    rows = [equation for factor in factors for equation in equations(field, factor)]
    planted = sum(point.x << (i * ell) for i, point in enumerate(points))
    for i in range(m - 2):
        planted |= partials[i].x << (m * ell + i * n)
    nvars = m * ell + (m - 2) * n
    assert (field.mod, target_x, nvars, len(rows)) == (
        expected['mod'], expected['target_x'], expected['nvars'],
        expected['factor_equations'])
    assert max(len(scope_of(row)) for row in rows) == expected['max_equation_support']
    assert sum(len(row) for row in rows) == expected['monomial_terms']
    assert all(satisfies(canonical(row), planted) for row in rows)
    return dict(n=n, m=m, ell=ell, seed=seed, nvars=nvars,
                modulus=field.mod, curve_b=1, target_x=target_x,
                planted_assignment=planted, equations=rows,
                structural_profile=expected)
