#!/usr/bin/env python3
"""Exact prime-norm T-tau table-shape screen for 15 scalar positions."""
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
INITIAL_RADIUS = 196462116142286827589391637123844718211
STEPS = 15


def prime(n):
    return n > 1 and all(n % d for d in range(2, isqrt(n)+1))


def norm(a, b):
    return a*a+3*a*b+3*b*b


def omega(pair):
    a, b = pair
    return a+3*b, -a-2*b


def digit(t, q, residue):
    if residue == 0:
        return 0, 0
    best = None
    for lift in (residue, residue-q):
        center = ((2*t-3)*lift+q)//(2*q)
        for b in (center-1, center, center+1):
            a = lift-t*b
            score = norm(a,b), abs(b), abs(a), a, b
            if best is None or score < best:
                best = score
    return best[3], best[4]


def terminal_full_count(radius):
    """Count N(a,b)<radius² through (2a+3b)²+3b²<4radius²."""
    count = 0
    for b in range(-2*radius, 2*radius+1):
        limit = 4*radius*radius-3*b*b-1
        if limit < 0:
            continue
        maximum = isqrt(limit)
        parity = b % 2
        first = -maximum + (parity+maximum) % 2
        if first <= maximum:
            count += (maximum-first)//2+1
    assert count % 6 == 1
    return count


def screen(t):
    q = t*t-3*t+3
    assert prime(q) and q % 6 == 1
    digits = [digit(t,q,r) for r in range(q)]
    assert all((a+t*b-r)%q == 0 for r,(a,b) in enumerate(digits))
    assert all(digits[q-r] == (-digits[r][0],-digits[r][1])
               for r in range(1,q))
    assert all(digits[((1-t)*r)%q] == omega(digits[r]) for r in range(q))
    maxnorm = max(norm(*pair) for pair in digits)
    digit_radius = isqrt(maxnorm-1)+1
    radii = [INITIAL_RADIUS]
    for _ in range(STEPS):
        nxt = isqrt((radii[-1]+digit_radius)**2//q)+1
        assert (radii[-1]+digit_radius)**2 < q*nxt*nxt
        radii.append(nxt)
    terminal_full = terminal_full_count(radii[-1])
    digit_seeds = (q-1)//6+1
    terminal_seeds = (terminal_full-1)//6+1
    return {
        't':t, 'radix':[t,-1], 'norm':q,
        'max_digit_norm':maxnorm, 'digit_radius':digit_radius,
        'terminal_radius':radii[-1], 'radius_sequence':radii,
        'digit_orbit_seeds':digit_seeds,
        'terminal_full_count':terminal_full,
        'terminal_orbit_seeds':terminal_seeds,
        'point_payload_bytes':64*(STEPS*digit_seeds+terminal_seeds),
        'sign_and_unit_covariance_residues':q,
    }


def main():
    rows = [screen(t) for t in range(240,321)
            if prime(t*t-3*t+3)]
    return {
        'schema':1, 'radix_family':'T-tau', 'positions':STEPS,
        't_range_inclusive':[240,320], 'prime_norm_rows':len(rows),
        'rows':rows,
        'payload_minimum':min(rows,key=lambda row:row['point_payload_bytes']),
        'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(main(),sort_keys=True,indent=2))
