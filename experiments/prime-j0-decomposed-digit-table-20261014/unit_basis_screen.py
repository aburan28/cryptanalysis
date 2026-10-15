#!/usr/bin/env python3
"""Exact unit-basis decomposition of the norm-19183 selected digits."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014'
spec = importlib.util.spec_from_file_location('radix140', PARENT / 'screen140.py')
radix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radix)


def split(pair):
    """Write a+b*tau = x+y*(1-tau), where x=a+b and y=-b."""
    a, b = pair
    x, y = a+b, -b
    assert (x+y, -y) == pair
    return x, y


def unit_bases():
    units = [(a, b) for a in range(-2, 3) for b in range(-2, 3)
             if radix.norm(a, b) == 1]
    assert len(units) == 6
    for u in units:
        for v in units:
            det = u[0]*v[1]-u[1]*v[0]
            if abs(det) == 1:
                yield u, v, det


def run():
    digits = radix.digits()
    assert len(digits) == radix.Q
    digit_coefficients = [split(pair) for pair in digits]
    digit_limit = max(max(abs(x), abs(y)) for x, y in digit_coefficients)
    assert digit_limit == 92

    radius = json.loads((PARENT / 'screen140.json').read_text())['terminal_radius']
    terminal = [(a, b) for a in range(-2*radius, 2*radius+1)
                for b in range(-2*radius, 2*radius+1)
                if radix.norm(a, b) < radius*radius]
    terminal_coefficients = [split(pair) for pair in terminal]
    terminal_limit = max(max(abs(x), abs(y)) for x, y in terminal_coefficients)
    assert terminal_limit == 90

    # A unit basis is the shortest possible Z-basis in this norm. Check all
    # oriented unit pairs for the chosen finite digit set.
    basis_scores = []
    for u, v, det in unit_bases():
        coefficients = [((v[1]*a-v[0]*b)//det,
                         (-u[1]*a+u[0]*b)//det) for a, b in digits]
        assert all(x*u[0]+y*v[0] == a and x*u[1]+y*v[1] == b
                   for (x, y), (a, b) in zip(coefficients, digits))
        bounds = (max(abs(x) for x, _ in coefficients),
                  max(abs(y) for _, y in coefficients))
        basis_scores.append((sum(bounds), bounds, u, v))
    assert min(row[0] for row in basis_scores) == 184

    scalar_fixture = HERE.parent / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(scalar_fixture.read_text())['cases']
    nonzero_components = 0
    both_nonzero = 0
    observed_terminal_limit = 0
    for case in cases:
        scalar = int(case['scalar_hex'], 16) % radix.nearest.model.mixed.screen.ORDER
        state = radix.nearest.model.mixed.screen.representative(scalar)
        for _ in range(radix.STEPS):
            state, pair = radix.step(state, digits)
            x, y = split(pair)
            assert max(abs(x), abs(y)) <= digit_limit
            nonzero_components += int(x != 0)+int(y != 0)
            both_nonzero += int(x != 0 and y != 0)
        assert radix.norm(*state) < radius*radius
        observed_terminal_limit = max(observed_terminal_limit,
                                      max(map(abs, split(state))))
    assert observed_terminal_limit <= terminal_limit

    return {
        'schema': 1, 'radix': [radix.T, -1], 'radix_norm': radix.Q,
        'unit_basis': [[1, 0], [1, -1]],
        'basis_identity': 'a+b*tau=(a+b)-b*(1-tau)',
        'positions': radix.STEPS, 'digit_count': len(digits),
        'digit_coefficient_limit': digit_limit,
        'terminal_radius': radius, 'terminal_full_count': len(terminal),
        'terminal_coefficient_limit': terminal_limit,
        'positive_points_per_digit_window': digit_limit,
        'positive_points_terminal_window': terminal_limit,
        'point_payload_bytes': 64*(radix.STEPS*digit_limit+terminal_limit),
        'unit_basis_min_sum_of_digit_bounds': min(row[0] for row in basis_scores),
        'unit_basis_count': len(basis_scores),
        'frozen_scalar_replays': len(cases),
        'frozen_nonzero_components': nonzero_components,
        'frozen_both_nonzero_digits': both_nonzero,
        'frozen_max_terminal_coefficient': observed_terminal_limit,
        'fixture_sha256': sha256(scalar_fixture.read_bytes()).hexdigest(),
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
