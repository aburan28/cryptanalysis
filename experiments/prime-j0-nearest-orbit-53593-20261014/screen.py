#!/usr/bin/env python3
"""Exact exploratory screen for the 16-position radix 233 - tau."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from math import isqrt
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-nearest-digit-12211-20261014"
ORBIT = HERE.parent / "prime-j0-nearest-orbit-12211-20261014"
spec = importlib.util.spec_from_file_location("nearest_12211_screen", PARENT / "screen.py")
nearest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nearest)
orbit_spec = importlib.util.spec_from_file_location("orbit_12211_screen", ORBIT / "screen.py")
orbit = importlib.util.module_from_spec(orbit_spec)
orbit_spec.loader.exec_module(orbit)

T = 233
Q = T * T - 3 * T + 3
STEPS = 16
PI = (T, -1)


def norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def score(a, b):
    return norm(a, b), abs(b), abs(a), a, b


def six_candidate_digit(residue):
    if residue == 0:
        return 0, 0
    best = None
    for lift in (residue, residue - Q):
        center = ((2 * T - 3) * lift + Q) // (2 * Q)
        for b in (center - 1, center, center + 1):
            a = lift - T * b
            candidate = score(a, b)
            if best is None or candidate < best:
                best = candidate
    return best[3], best[4]


def digits():
    return [six_candidate_digit(residue) for residue in range(Q)]


def full_global_minimum_check(selected, maxnorm):
    # N(a,b) >= 3b^2/4 bounds every potential improvement.
    bound = isqrt(4 * maxnorm // 3) + 1
    for residue in range((Q + 1) // 2):
        best = score(*selected[residue])
        wider = None
        for b in range(-bound, bound + 1):
            base = residue - T * b
            center = (-3 * b - 2 * base + Q) // (2 * Q)
            for offset in (-1, 0, 1):
                a = base + (center + offset) * Q
                candidate = score(a, b)
                if wider is None or candidate < wider:
                    wider = candidate
        assert best == wider, (residue, best, wider)
    return bound, (Q + 1) // 2


def step(pair, selected):
    a, b = pair
    da, db = selected[(a + T * b) % Q]
    shifted_b = b - db
    quotient, remainder = divmod(a - da + T * shifted_b, Q)
    assert remainder == 0
    next_pair = ((T - 3) * quotient - shifted_b, quotient)
    product = nearest.multiply(PI, next_pair)
    assert (a, b) == (da + product[0], db + product[1])
    return next_pair, (da, db)


def run(full_global=False):
    selected = digits()
    assert Q == 53593
    assert all((a + T * b - r) % Q == 0 for r, (a, b) in enumerate(selected))
    assert all(selected[Q - r] == (-selected[r][0], -selected[r][1])
               for r in range(1, Q))
    assert all(selected[((1 - T) * r) % Q] == orbit.omega(selected[r])
               for r in range(Q))
    maxnorm = max(norm(*pair) for pair in selected)
    assert maxnorm == 17787
    wide_bound, checked = full_global_minimum_check(selected, maxnorm) if full_global else (None, 0)
    digit_seeds = sorted({orbit.canonical(pair) for pair in selected})
    assert Counter(Counter(orbit.canonical(pair) for pair in selected).values()) == {6: 8932, 1: 1}
    assert len(digit_seeds) == 8933
    seed_index = {pair: index for index, pair in enumerate(digit_seeds)}
    codes = [(seed_index[orbit.canonical(pair)], *orbit.encode(pair, orbit.canonical(pair)))
             for pair in selected]
    assert all(tuple(orbit.images(digit_seeds[index]))[2 * power + sign][0] == selected[r]
               for r, (index, power, sign) in enumerate(codes))

    digit_radius = isqrt(maxnorm - 1) + 1
    order = nearest.model.mixed.screen.ORDER
    radii = [isqrt(order // 3) + 1]
    for _ in range(STEPS):
        old = radii[-1]
        radii.append(isqrt((old + digit_radius) ** 2 // Q) + 1)
    assert all((radii[i] + digit_radius) ** 2 < Q * radii[i + 1] ** 2
               for i in range(STEPS))
    assert radii[-1] == 4
    terminal = [(a, b) for a in range(-8, 9) for b in range(-8, 9)
                if norm(a, b) < radii[-1] ** 2]
    terminal_seeds = sorted({orbit.canonical(pair) for pair in terminal})
    assert all(any(value == pair for value, _, _ in orbit.images(orbit.canonical(pair)))
               for pair in terminal)

    fixture = PARENT / "../prime-j0-mixed640-materialized-tree-20261013/selective-holdout.json"
    cases = json.loads(fixture.read_text())["cases"]
    digest = sha256()
    max_terminal_norm = 0
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % order
        representative = nearest.model.mixed.screen.representative(scalar)
        state = representative
        trace = []
        for _ in range(STEPS):
            state, digit = step(state, selected)
            trace.append(digit)
        max_terminal_norm = max(max_terminal_norm, norm(*state))
        assert norm(*state) < radii[-1] ** 2
        for digit in reversed(trace):
            product = nearest.multiply(PI, state)
            state = product[0] + digit[0], product[1] + digit[1]
        assert state == representative
        assert (state[0] + state[1] * nearest.model.reference.LAMBDA_TAU - scalar) % order == 0
        digest.update(state[0].to_bytes(17, "big", signed=True))
        digest.update(state[1].to_bytes(17, "big", signed=True))

    return {
        "schema": 1,
        "radix": list(PI),
        "radix_norm": Q,
        "positions": STEPS,
        "digit_max_norm": maxnorm,
        "digit_radius": digit_radius,
        "terminal_radius": radii[-1],
        "radius_sequence": radii,
        "terminal_full_count": len(terminal),
        "terminal_orbit_count": len(terminal_seeds),
        "digit_orbit_count": len(digit_seeds),
        "point_payload_bytes": (STEPS * len(digit_seeds) + len(terminal_seeds)) * 64,
        "global_minimum_checked": full_global,
        "global_minimum_canonical_residues": checked,
        "global_minimum_b_bound": wide_bound,
        "unit_covariance_residues": Q,
        "frozen_scalar_replays": len(cases),
        "max_frozen_terminal_norm": max_terminal_norm,
        "representative_replay_sha256": digest.hexdigest(),
        "fixture_sha256": sha256(fixture.read_bytes()).hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-global", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.full_global), sort_keys=True, indent=2))
