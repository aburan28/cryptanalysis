#!/usr/bin/env python3
"""Exact arithmetic and frozen scalar panel for the radix-943 candidate."""

import hashlib
import json
from math import gcd, isqrt
from pathlib import Path
import random


ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
LAMBDA_TAU = int("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
RADIX = 943
WINDOWS = 13
SEED = 20261009
CASES = 4096


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def nearest_representative(scalar):
    fw = scalar * V[1] // ORDER
    fv = -(scalar * W[1]) // ORDER
    choices = []
    for i in (fw, fw + 1):
        for j in (fv, fv + 1):
            a = scalar - i * W[0] - j * V[0]
            b = -i * W[1] - j * V[1]
            choices.append((norm((a, b)), max(abs(a), abs(b)), a, b))
    _, _, a, b = min(choices)
    return a, b


def nearest_digit(pair):
    a, b = pair
    u, v = a + b, -b
    fu, fv = u // RADIX, v // RADIX
    choices = []
    for m in (fu, fu + 1):
        for n in (fv, fv + 1):
            x, y = u - m * RADIX, v - n * RADIX
            d = x + y, -y
            choices.append((norm(d), d[0], d[1]))
    _, da, db = min(choices)
    return da, db


def recode(scalar):
    start = nearest_representative(scalar)
    a, b = start
    digits = []
    for _ in range(WINDOWS):
        da, db = nearest_digit((a, b))
        assert (a - da) % RADIX == (b - db) % RADIX == 0
        assert 3 * norm((da, db)) <= RADIX * RADIX
        digits.append((da, db))
        a, b = (a - da) // RADIX, (b - db) // RADIX
    assert (a, b) == (0, 0)
    rebuilt = (sum(d[0] * RADIX ** i for i, d in enumerate(digits)),
               sum(d[1] * RADIX ** i for i, d in enumerate(digits)))
    assert rebuilt == start
    assert (start[0] + start[1] * LAMBDA_TAU - scalar) % ORDER == 0
    return start, digits


def main():
    assert U[0] * V[1] - U[1] * V[0] == ORDER
    assert norm(W) == norm(V) == norm((W[0] + V[0], W[1] + V[1])) == ORDER
    assert gcd(RADIX, 6) == 1
    ceil_sqrt_order = isqrt(ORDER) + 1
    geometric_sum = sum(RADIX ** j for j in range(1, WINDOWS + 1))
    left = (ceil_sqrt_order + geometric_sum) ** 2
    right = 3 * RADIX ** (2 * WINDOWS)
    assert left < right
    orbit_entries = (RADIX * RADIX + 5) // 6
    assert 1 + (RADIX * RADIX - 1) // 6 == orbit_entries == 148209

    # The atlas's entire residue domain is checked, independently of input law.
    residue_count = 0
    max_digit_norm = 0
    for a in range(RADIX):
        for b in range(RADIX):
            digit = nearest_digit((a, b))
            assert (digit[0] % RADIX, digit[1] % RADIX) == (a, b)
            digit_norm = norm(digit)
            assert 3 * digit_norm <= RADIX * RADIX
            max_digit_norm = max(max_digit_norm, digit_norm)
            residue_count += 1

    fixture = [0, 1, 2, ORDER - 2, ORDER - 1]
    rng = random.Random(SEED)
    scalars = fixture + [rng.getrandbits(256) % ORDER for _ in range(CASES)]
    digest = hashlib.sha256()
    histogram = {}
    max_initial_norm = 0
    for scalar in scalars:
        digest.update(scalar.to_bytes(32, "big"))
        start, digits = recode(scalar)
        initial_norm = norm(start)
        assert 3 * initial_norm <= ORDER
        max_initial_norm = max(max_initial_norm, initial_norm)
        additions = max(0, sum(d != (0, 0) for d in digits) - 1)
        histogram[str(additions)] = histogram.get(str(additions), 0) + 1

    result = {
        "schema": 1,
        "radix": RADIX,
        "windows": WINDOWS,
        "scalar_seed": SEED,
        "random_cases": CASES,
        "boundary_cases": len(fixture),
        "scalar_input_sha256": digest.hexdigest(),
        "scalar_reconstructions": len(scalars),
        "residue_pairs_checked": residue_count,
        "max_digit_norm": max_digit_norm,
        "max_initial_norm": str(max_initial_norm),
        "geometric_inequality_left": str(left),
        "geometric_inequality_right": str(right),
        "inequality_verified": left < right,
        "orbit_entries_per_window": orbit_entries,
        "point_entries": WINDOWS * orbit_entries,
        "point_bytes": WINDOWS * orbit_entries * 72,
        "addition_histogram": histogram,
        "wall_time_ms": None,
    }
    out = Path(__file__).with_name("radix943-screen-result.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"point_entries": result["point_entries"],
                      "scalar_reconstructions": len(scalars),
                      "addition_histogram": histogram}, sort_keys=True))


if __name__ == "__main__":
    main()
