#!/usr/bin/env python3
"""Exact table-shape screen of prime-norm 16-position T-tau radices."""
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
INITIAL_RADIUS = 196462116142286827589391637123844718211


def norm(a, b):
    return a*a + 3*a*b + 3*b*b


def prime(q):
    return all(q % d for d in range(2, isqrt(q)+1))


def omega(pair):
    a, b = pair
    return a+3*b, -a-2*b


def canonical(pair):
    choices = []
    for _ in range(3):
        choices.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return min(choices)


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


def screen(t):
    q = t*t-3*t+3
    assert prime(q)
    digits = [digit(t,q,r) for r in range(q)]
    assert all((a+t*b-r)%q == 0 for r,(a,b) in enumerate(digits))
    assert all(digits[q-r] == (-digits[r][0],-digits[r][1]) for r in range(1,q))
    assert all(digits[((1-t)*r)%q] == omega(digits[r]) for r in range(q))
    maxnorm = max(norm(*pair) for pair in digits)
    digit_radius = isqrt(maxnorm-1)+1
    radius = INITIAL_RADIUS
    for _ in range(16):
        radius = isqrt((radius+digit_radius)**2//q)+1
    terminal = [(a,b) for a in range(-2*radius,2*radius+1)
                for b in range(-2*radius,2*radius+1)
                if norm(a,b) < radius*radius]
    digit_seeds = len({canonical(pair) for pair in digits})
    terminal_seeds = len({canonical(pair) for pair in terminal})
    return {'t':t, 'norm':q, 'max_digit_norm':maxnorm,
            'digit_radius':digit_radius, 'terminal_radius':radius,
            'digit_orbit_seeds':digit_seeds,
            'terminal_orbit_seeds':terminal_seeds,
            'point_payload_bytes':64*(16*digit_seeds+terminal_seeds),
            'sign_and_unit_covariance_residues':q}


def main():
    rows = [screen(t) for t in range(180,234)
            if prime(t*t-3*t+3)]
    return {'schema':1, 'radix_family':'T-tau', 'positions':16,
            't_range_inclusive':[180,233], 'prime_norm_rows':len(rows),
            'rows':rows, 'payload_minimum':min(rows,key=lambda row:row['point_payload_bytes']),
            'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(),sort_keys=True,indent=2))
