#!/usr/bin/env python3
"""Exact 17-position 140-tau digit, orbit, terminal, and recoding screen."""
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
PARENT = EXPERIMENTS / 'prime-j0-nearest-digit-12211-20261014'
ORBIT = EXPERIMENTS / 'prime-j0-nearest-orbit-12211-20261014'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nearest = load('nearest_12211_screen_for_140', PARENT / 'screen.py')
orbit = load('orbit_12211_screen_for_140', ORBIT / 'screen.py')
T, Q, STEPS = 140, 19183, 17
PI = (T, -1)


def norm(a, b):
    return a*a + 3*a*b + 3*b*b


def score(a, b):
    return norm(a, b), abs(b), abs(a), a, b


def digit(residue):
    if residue == 0:
        return 0, 0
    best = None
    for lift in (residue, residue-Q):
        center = ((2*T-3)*lift+Q)//(2*Q)
        for b in (center-1, center, center+1):
            a = lift-T*b
            candidate = score(a, b)
            if best is None or candidate < best:
                best = candidate
    return best[3], best[4]


def digits():
    return [digit(residue) for residue in range(Q)]


def global_minimum_check(selected, maxnorm):
    bound = isqrt(4*maxnorm//3)+1
    for residue in range((Q+1)//2):
        best = score(*selected[residue])
        wider = None
        for b in range(-bound, bound+1):
            base = residue-T*b
            center = (-3*b-2*base+Q)//(2*Q)
            for offset in (-1, 0, 1):
                a = base+(center+offset)*Q
                candidate = score(a, b)
                if wider is None or candidate < wider:
                    wider = candidate
        assert best == wider, (residue, best, wider)
    return bound


def step(pair, selected):
    a, b = pair
    da, db = selected[(a+T*b)%Q]
    shifted_b = b-db
    quotient, remainder = divmod(a-da+T*shifted_b, Q)
    assert remainder == 0
    next_pair = ((T-3)*quotient-shifted_b, quotient)
    product = nearest.multiply(PI, next_pair)
    assert (a, b) == (da+product[0], db+product[1])
    return next_pair, (da, db)


def run():
    assert Q == T*T-3*T+3
    selected = digits()
    assert all((a+T*b-r)%Q == 0 for r, (a, b) in enumerate(selected))
    assert all(selected[Q-r] == (-selected[r][0], -selected[r][1])
               for r in range(1, Q))
    assert all(selected[((1-T)*r)%Q] == orbit.omega(selected[r])
               for r in range(Q))
    maxnorm = max(norm(*pair) for pair in selected)
    global_b_bound = global_minimum_check(selected, maxnorm)
    digit_radius = isqrt(maxnorm-1)+1
    order = nearest.model.mixed.screen.ORDER
    radii = [isqrt(order//3)+1]
    for _ in range(STEPS):
        radius = isqrt((radii[-1]+digit_radius)**2//Q)+1
        radii.append(radius)
    assert all((radii[i]+digit_radius)**2 < Q*radii[i+1]**2
               for i in range(STEPS))
    terminal_radius = radii[-1]
    terminal = [(a, b) for a in range(-2*terminal_radius, 2*terminal_radius+1)
                for b in range(-2*terminal_radius, 2*terminal_radius+1)
                if norm(a, b) < terminal_radius**2]
    seeds = {orbit.canonical(pair) for pair in selected}
    terminal_seeds = {orbit.canonical(pair) for pair in terminal}
    assert Counter(Counter(orbit.canonical(pair) for pair in selected).values()) == {
        6: (Q-1)//6, 1: 1}

    source = EXPERIMENTS / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(source.read_text())['cases']
    digest = sha256()
    observed_terminal_norm = 0
    for case in cases:
        scalar = int(case['scalar_hex'], 16) % order
        initial = nearest.model.mixed.screen.representative(scalar)
        state = initial
        trace = []
        for _ in range(STEPS):
            state, selected_digit = step(state, selected)
            trace.append(selected_digit)
        observed_terminal_norm = max(observed_terminal_norm, norm(*state))
        assert norm(*state) < terminal_radius**2
        for selected_digit in reversed(trace):
            product = nearest.multiply(PI, state)
            state = product[0]+selected_digit[0], product[1]+selected_digit[1]
        assert state == initial
        assert (state[0]+state[1]*nearest.model.reference.LAMBDA_TAU-scalar)%order == 0
        digest.update(state[0].to_bytes(17, 'big', signed=True))
        digest.update(state[1].to_bytes(17, 'big', signed=True))

    return {
        'schema': 1, 'radix': list(PI), 'radix_norm': Q,
        'positions': STEPS, 'max_digit_norm': maxnorm,
        'digit_radius': digit_radius, 'terminal_radius': terminal_radius,
        'radius_sequence': radii, 'digit_orbit_count': len(seeds),
        'terminal_orbit_count': len(terminal_seeds),
        'terminal_full_count': len(terminal),
        'point_payload_bytes': 64*(STEPS*len(seeds)+len(terminal_seeds)),
        'global_minimum_canonical_residues': (Q+1)//2,
        'global_minimum_b_bound': global_b_bound,
        'sign_and_unit_covariance_residues': Q,
        'frozen_scalar_replays': len(cases),
        'max_frozen_terminal_norm': observed_terminal_norm,
        'representative_replay_sha256': digest.hexdigest(),
        'fixture_sha256': sha256(source.read_bytes()).hexdigest(),
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
