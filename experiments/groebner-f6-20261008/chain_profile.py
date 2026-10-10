"""Measure exact Boolean support width of an S3 auxiliary-coordinate chain."""
import argparse
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'pdp-scaling'))
from gf2n import GF2n, Curve

from separator import scope_of


def add(*polys):
    out = {}
    for poly in polys:
        for mask, coefficient in poly.items():
            out[mask] = out.get(mask, 0) ^ coefficient
            if not out[mask]:
                del out[mask]
    return out


def mul(field, left, right):
    out = {}
    for a, coefficient_a in left.items():
        for b, coefficient_b in right.items():
            mask = a | b
            out[mask] = out.get(mask, 0) ^ field.mul(coefficient_a, coefficient_b)
            if not out[mask]:
                del out[mask]
    return out


def coordinate(offset, width):
    return {1 << (offset + i): 1 << i for i in range(width)}


def square(field, linear):
    return {mask: field.mul(coefficient, coefficient)
            for mask, coefficient in linear.items()}


def s3(field, b, x, y, z):
    x2, y2, z2 = (square(field, value) for value in (x, y, z))
    return add(mul(field, x2, y2), mul(field, x2, z2),
               mul(field, y2, z2), mul(field, mul(field, x, y), z), {0: b})


def equations(field, poly):
    result = [[] for _ in range(field.n)]
    for mask, coefficient in poly.items():
        for bit in range(field.n):
            if coefficient >> bit & 1:
                result[bit].append(mask)
    return result


def induced_width(scopes, nvars, order=None):
    active = [set(scope) for scope in scopes]
    remaining = set(range(nvars))
    if order is not None:
        assert len(order) == nvars and set(order) == remaining
        order = iter(order)
    width, states = 0, 0
    while remaining:
        def score(variable):
            bag = {variable}
            for scope in active:
                if variable in scope:
                    bag.update(scope)
            return len(bag), variable
        variable = min(remaining, key=score) if order is None else next(order)
        bag = {variable}
        kept = []
        for scope in active:
            if variable in scope:
                bag.update(scope)
            else:
                kept.append(scope)
        width = max(width, len(bag))
        states += 1 << len(bag)
        kept.append(bag - {variable})
        active = kept
        remaining.remove(variable)
    return width, states


def profile(n, m, ell, seed):
    if not (3 <= m and 1 <= ell <= n and m*ell + (m-2)*n <= 64):
        raise ValueError('chain requires m>=3, ell<=n, and at most 64 Boolean variables')
    field = GF2n(n)
    b = 1
    curve = Curve(field, b)
    rng = random.Random(seed)
    for fixture_attempt in range(1, 1001):
        points = [curve.random_factor_base_point(ell, rng) for _ in range(m)]
        partials = [curve.sum(points[:i]) for i in range(2, m+1)]
        if all(not point.inf for point in partials):
            break
    else:
        raise ValueError('could not construct finite intermediate points in 1000 attempts')
    target_x = partials[-1].x
    planted = sum(point.x << (i*ell) for i, point in enumerate(points))
    summands = [coordinate(i*ell, ell) for i in range(m)]
    auxiliaries = [coordinate(m*ell + i*n, n) for i in range(m-2)]
    factors = [s3(field, b, summands[0], summands[1], auxiliaries[0])]
    for i in range(1, m-2):
        factors.append(s3(field, b, auxiliaries[i-1], summands[i+1], auxiliaries[i]))
    factors.append(s3(field, b, auxiliaries[-1], summands[-1], {0: target_x}))
    all_equations = [equations(field, factor) for factor in factors]
    assignment = planted
    for i in range(m-2):
        assignment |= partials[i].x << (m*ell+i*n)
    assert all(sum((mask & assignment) == mask for mask in eq) % 2 == 0
               for group in all_equations for eq in group)
    scopes = [scope_of(eq) for group in all_equations for eq in group]
    width, state_upper_bound = induced_width(scopes, m*ell+(m-2)*n)
    summand_order = [list(range(i*ell, (i+1)*ell)) for i in range(m)]
    auxiliary_order = [list(range(m*ell+i*n, m*ell+(i+1)*n)) for i in range(m-2)]
    left_to_right = summand_order[0]+summand_order[1]
    for i in range(m-3):
        left_to_right += auxiliary_order[i]+summand_order[i+2]
    left_to_right += auxiliary_order[-1]+summand_order[-1]
    left_width, left_states = induced_width(scopes, m*ell+(m-2)*n, left_to_right)
    theorem_bound = n+2*ell if m == 3 else max(n+2*ell, 2*n+ell)
    assert left_width <= theorem_bound
    return dict(status='PLANTED_CHAIN_EQUATIONS_VERIFIED', n=n, m=m, ell=ell,
                seed=seed, fixture_attempt=fixture_attempt, mod=field.mod,
                curve_b=b, target_x=target_x,
                nvars=m*ell+(m-2)*n, factor_equations=len(scopes),
                monomial_terms=sum(len(eq) for group in all_equations for eq in group),
                max_equation_support=max(map(len, scopes)), induced_width=width,
                enumerated_state_upper_bound=state_upper_bound,
                left_to_right_width=left_width,
                left_to_right_state_upper_bound=left_states,
                theorem_bound=theorem_bound,
                factor_support_maxima=[max(map(len, map(scope_of, group)))
                                       for group in all_equations])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=9)
    parser.add_argument('--m', type=int, action='append')
    parser.add_argument('--ell', type=int, default=3)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rows = [profile(args.n, m, args.ell, args.seed) for m in (args.m or [3, 4, 5, 6])]
    encoded = json.dumps(rows, indent=2)+'\n'
    if args.output:
        assert not args.output.exists()
        args.output.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
