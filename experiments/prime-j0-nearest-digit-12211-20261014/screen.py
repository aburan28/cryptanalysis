#!/usr/bin/env python3
"""Exact minimum-norm representatives of Z[tau]/(112-tau)."""
import json
from collections import Counter
from hashlib import sha256
from math import isqrt
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-mixed640-materialized-tree-20261013'
sys.path.insert(0, str(PARENT))
import model  # noqa: E402

Q = 12211
STEPS = 18
PI = (112, -1)
FIXTURE = PARENT / 'selective-holdout.json'


def norm(a, b):
    return a*a + 3*a*b + 3*b*b


def multiply(x, y):
    a, b = x
    c, d = y
    return a*c-3*b*d, a*d+b*c+3*b*d


def digit_for_residue(r):
    if r == 0:
        return (0, 0)
    best = None
    # Any candidate with norm at most 7500 has |b| <= 100. The search
    # itself verifies the much smaller actual maximum afterward.
    for b in range(-100, 101):
        base = r - 112*b
        center = (-(2*base + 3*b) + Q) // (2*Q)
        for k in (center-1, center, center+1):
            a = base + k*Q
            score = (norm(a, b), abs(b), abs(a), a, b)
            if best is None or score < best[0]:
                best = (score, (a, b))
    return best[1]


def six_candidate_digit(r):
    """Two congruent lifts, each with three quotient estimates."""
    candidates = []
    for lift in (r, r-Q):
        center = (2*lift + 110) // 221
        for b in (center-1, center, center+1):
            a = lift - 112*b
            candidates.append((norm(a,b), abs(b), abs(a), a, b))
    best = min(candidates)
    return best[3], best[4]


def digits():
    result = [(0, 0)] * Q
    for r in range(1, (Q+1)//2):
        pair = digit_for_residue(r)
        result[r] = pair
        result[Q-r] = (-pair[0], -pair[1])
    return result


def step(pair, lookup):
    a, b = pair
    da, db = lookup[(a + 112*b) % Q]
    shifted_b = b - db
    k, rem = divmod(a - da + 112*shifted_b, Q)
    assert rem == 0
    nxt = (109*k-shifted_b, k)
    product = multiply(PI, nxt)
    assert (a, b) == (da+product[0], db+product[1])
    return nxt, (da, db)


def radii(order, d):
    result = [isqrt(order//3)+1]
    for _ in range(STEPS):
        old = result[-1]
        result.append(isqrt((old+d)**2//Q)+1)
    assert order < 3*result[0]**2
    assert all((result[i]+d)**2 < Q*result[i+1]**2 for i in range(STEPS))
    return result


def run():
    lookup = digits()
    assert all((a+112*b-r) % Q == 0 for r,(a,b) in enumerate(lookup))
    assert all(lookup[Q-r] == (-lookup[r][0],-lookup[r][1]) for r in range(1,(Q+1)//2))
    maxnorm = max(norm(*p) for p in lookup)
    d = isqrt(maxnorm-1)+1
    assert maxnorm <= 7500
    assert all(norm(*digit_for_residue(r)) == norm(*lookup[r]) for r in range(Q))
    assert all(six_candidate_digit(r) == lookup[r] for r in range((Q+1)//2))
    radius = radii(model.mixed.screen.ORDER,d)
    terminal = [(a,b) for a in range(2*radius[-1])
                for b in range(-2*radius[-1],2*radius[-1]+1)
                if (a>0 or b>=0) and norm(a,b)<radius[-1]**2]
    cases = json.loads(FIXTURE.read_text())['cases']
    counts = Counter()
    max_terminal_norm = 0
    h = sha256()
    for case in cases:
        scalar = int(case['scalar_hex'],16) % model.mixed.screen.ORDER
        pair = model.mixed.screen.representative(scalar)
        state = pair
        trace = []
        for _ in range(STEPS):
            state,digit = step(state,lookup)
            trace.append(digit)
        terminal_point = state
        for digit in reversed(trace):
            product = multiply(PI,state)
            state = (product[0]+digit[0],product[1]+digit[1])
        assert state == pair
        assert (pair[0]+pair[1]*model.reference.LAMBDA_TAU-scalar) % model.mixed.screen.ORDER == 0
        assert norm(*terminal_point)<radius[-1]**2
        counts[sum(d!=(0,0) for d in trace)] += 1
        max_terminal_norm=max(max_terminal_norm,norm(*terminal_point))
        h.update(pair[0].to_bytes(17,'big',signed=True))
        h.update(pair[1].to_bytes(17,'big',signed=True))
    digit_payload = STEPS*((Q+1)//2)*64
    terminal_payload = len(terminal)*64
    return {'schema':1,'pi':list(PI),'norm':Q,'steps':STEPS,
            'digit_max_norm':maxnorm,'digit_norm_cap':d,
            'digit_sign_canonical_count':(Q+1)//2,
            'six_candidate_matches_full_search':True,
            'radius_sequence':radius,'terminal_radius':radius[-1],
            'terminal_sign_canonical_pairs':len(terminal),
            'minimum_payload_bytes_before_metadata':digit_payload+terminal_payload,
            'digit_payload_bytes':digit_payload,'terminal_payload_bytes':terminal_payload,
            'residue_lut_bytes_if_i16_pairs':4*Q,
            'fixture_cases':len(cases),'fixture_max_terminal_norm':max_terminal_norm,
            'fixture_nonzero_digit_counts':dict(sorted(counts.items())),
            'fixture_sha256':sha256(FIXTURE.read_bytes()).hexdigest(),
            'representative_replay_sha256':h.hexdigest(),
            'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}

if __name__ == '__main__':
    print(json.dumps(run(),indent=2,sort_keys=True))
