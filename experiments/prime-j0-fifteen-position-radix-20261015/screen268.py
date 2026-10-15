#!/usr/bin/env python3
"""Exact selected-digit and 15-step recoding screen for pi=268-tau."""
from hashlib import sha256
import importlib.util
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
PARENT = EXPERIMENTS / 'prime-j0-variable-orbit-radix-20261014'
spec = importlib.util.spec_from_file_location('radix140', PARENT / 'screen140.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
nearest, orbit = model.nearest, model.orbit
T, Q, STEPS = 268, 71023, 15


def norm(a, b):
    return a*a+3*a*b+3*b*b


def score(a, b):
    return norm(a,b), abs(b), abs(a), a, b


def digit(residue):
    if residue == 0:
        return 0, 0
    best = None
    for lift in (residue, residue-Q):
        center = ((2*T-3)*lift+Q)//(2*Q)
        for b in (center-1,center,center+1):
            a = lift-T*b
            candidate = score(a,b)
            if best is None or candidate < best:
                best = candidate
    return best[3],best[4]


def digits():
    return [digit(r) for r in range(Q)]


def global_minimum_check(selected, maxnorm):
    bound = isqrt(4*maxnorm//3)+1
    for residue in range((Q+1)//2):
        best = score(*selected[residue])
        wider = None
        for b in range(-bound,bound+1):
            base = residue-T*b
            center = (-3*b-2*base+Q)//(2*Q)
            for offset in (-1,0,1):
                a = base+(center+offset)*Q
                candidate = score(a,b)
                if wider is None or candidate < wider:
                    wider = candidate
        assert best == wider, (residue,best,wider)
    return bound


def step(pair, selected):
    a,b = pair
    da,db = selected[(a+T*b)%Q]
    shifted_b = b-db
    quotient,remainder = divmod(a-da+T*shifted_b,Q)
    assert remainder == 0
    next_pair = ((T-3)*quotient-shifted_b,quotient)
    product = nearest.multiply((T,-1),next_pair)
    assert (a,b) == (da+product[0],db+product[1])
    return next_pair,(da,db)


def run():
    assert Q == T*T-3*T+3
    frontier = json.loads((HERE / 'frontier15.json').read_text())
    shape = next(row for row in frontier['rows'] if row['t'] == T)
    selected = digits()
    assert all((a+T*b-r)%Q == 0 for r,(a,b) in enumerate(selected))
    assert all(selected[Q-r] == (-selected[r][0],-selected[r][1])
               for r in range(1,Q))
    assert all(selected[((1-T)*r)%Q] == orbit.omega(selected[r])
               for r in range(Q))
    maxnorm = max(norm(*pair) for pair in selected)
    assert maxnorm == shape['max_digit_norm']
    global_bound = global_minimum_check(selected,maxnorm)
    terminal_radius = shape['terminal_radius']
    terminal = [(a,b) for a in range(-2*terminal_radius,2*terminal_radius+1)
                for b in range(-2*terminal_radius,2*terminal_radius+1)
                if norm(a,b) < terminal_radius*terminal_radius]
    assert len(terminal) == shape['terminal_full_count']
    assert len({orbit.canonical(pair) for pair in selected}) == shape['digit_orbit_seeds']
    assert len({orbit.canonical(pair) for pair in terminal}) == shape['terminal_orbit_seeds']

    source = EXPERIMENTS / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(source.read_text())['cases']
    order = nearest.model.mixed.screen.ORDER
    digest = sha256()
    max_terminal_norm = 0
    for case in cases:
        scalar = int(case['scalar_hex'],16)%order
        initial = nearest.model.mixed.screen.representative(scalar)
        state = initial
        trace = []
        for _ in range(STEPS):
            state,selected_digit = step(state,selected)
            trace.append(selected_digit)
        max_terminal_norm = max(max_terminal_norm,norm(*state))
        assert norm(*state) < terminal_radius*terminal_radius
        for selected_digit in reversed(trace):
            product = nearest.multiply((T,-1),state)
            state = product[0]+selected_digit[0],product[1]+selected_digit[1]
        assert state == initial
        assert (state[0]+state[1]*nearest.model.reference.LAMBDA_TAU-scalar)%order == 0
        digest.update(state[0].to_bytes(17,'big',signed=True))
        digest.update(state[1].to_bytes(17,'big',signed=True))

    return {
        'schema':1,'radix':[T,-1],'radix_norm':Q,'positions':STEPS,
        'max_digit_norm':maxnorm,'digit_radius':shape['digit_radius'],
        'terminal_radius':terminal_radius,
        'radius_sequence':shape['radius_sequence'],
        'digit_orbit_count':shape['digit_orbit_seeds'],
        'terminal_orbit_count':shape['terminal_orbit_seeds'],
        'terminal_full_count':len(terminal),
        'point_payload_bytes':shape['point_payload_bytes'],
        'global_minimum_canonical_residues':(Q+1)//2,
        'global_minimum_b_bound':global_bound,
        'sign_and_unit_covariance_residues':Q,
        'frozen_scalar_replays':len(cases),
        'max_frozen_terminal_norm':max_terminal_norm,
        'representative_replay_sha256':digest.hexdigest(),
        'fixture_sha256':sha256(source.read_bytes()).hexdigest(),
        'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(run(),sort_keys=True,indent=2))
