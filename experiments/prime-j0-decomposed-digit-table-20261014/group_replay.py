#!/usr/bin/env python3
"""Independent secp256k1 point replay for the unit-basis digit table."""
from hashlib import sha256
import json
from pathlib import Path
import unit_basis_screen as screen

HERE = Path(__file__).resolve().parent
radix = screen.radix
reference = radix.nearest.model.reference


def main():
    digits = radix.digits()
    source = HERE.parent / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(source.read_text())['cases']
    order = radix.nearest.model.mixed.screen.ORDER
    fresh_seed = b'nearest-orbit-19183-fresh-v1'
    fresh = [int.from_bytes(sha256(fresh_seed+i.to_bytes(4, 'big')).digest(),
                            'big') % order for i in range(256)]
    fresh += [0, 1, order-1, 1 << 255]
    scalars = [int(case['scalar_hex'], 16) % order for case in cases] + fresh

    bases = []
    base = reference.G
    for _ in range(radix.STEPS+1):
        bases.append(base)
        base = reference.add(reference.multiply(radix.T, base),
                             reference.negate(reference.tau_point(base)))

    table = {}
    addends = 0
    omega_calls = 0
    output_digest = sha256()

    def multiple(window, magnitude):
        if magnitude == 0:
            return None
        key = window, magnitude
        if key not in table:
            table[key] = reference.multiply(magnitude, bases[window])
        return table[key]

    def split_point(window, pair):
        nonlocal addends, omega_calls
        x, y = screen.split(pair)
        limit = 92 if window < radix.STEPS else 90
        assert max(abs(x), abs(y)) <= limit
        first = multiple(window, abs(x))
        second = multiple(window, abs(y))
        if y:
            second = reference.omega_point(second)
            omega_calls += 1
        if x < 0:
            first = reference.negate(first)
        if y < 0:
            second = reference.negate(second)
        addends += int(x != 0)+int(y != 0)
        return reference.add(first, second)

    for scalar in scalars:
        state = radix.nearest.model.mixed.screen.representative(scalar)
        total = None
        for window in range(radix.STEPS):
            state, digit = radix.step(state, digits)
            total = reference.add(total, split_point(window, digit))
        total = reference.add(total, split_point(radix.STEPS, state))
        assert total == reference.multiply(scalar, reference.G)
        if total is None:
            output_digest.update(bytes(64))
        else:
            output_digest.update(total[0].to_bytes(32, 'big'))
            output_digest.update(total[1].to_bytes(32, 'big'))

    baseline = json.loads((HERE.parent / 'prime-j0-variable-orbit-radix-20261014' /
                           'group-replay140.json').read_text())
    assert output_digest.hexdigest() == baseline['output_point_sha256']
    return {
        'schema': 1, 'independent_scalar_replays': len(scalars),
        'frozen_case_count': len(cases), 'fresh_case_count': len(fresh),
        'unit_point_maps': omega_calls,
        'nonzero_digit_and_terminal_addends': addends,
        'touched_precomputed_points': len(table),
        'output_point_sha256': output_digest.hexdigest(),
        'matches_orbit_baseline_digest': True,
        'fixture_sha256': sha256(source.read_bytes()).hexdigest(),
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True, indent=2))
