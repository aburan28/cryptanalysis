#!/usr/bin/env python3
"""Retrospective x-only endomorphism and differential-addition controls.

This script uses the existing 64-base fixture only.  Affine group operations
are independent correctness oracles, not candidate timing measurements.
"""

import hashlib
import json
from pathlib import Path


P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
B = 7
HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"


def inv(value):
    return pow(value % P, P - 2, P)


def affine_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if left == right:
        slope = 3 * x1 * x1 * inv(2 * y1) % P
    else:
        slope = (y2 - y1) * inv(x2 - x1) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def xz_affine(pair):
    x, z = pair
    return None if z % P == 0 else x * inv(z) % P


def xz_tau(pair, beta):
    x, z = pair
    x2 = x * x % P
    z2 = z * z % P
    # x(tau P) = (x^3+4b)/((1-beta)^2*x^2).
    return ((x2 * x + 4 * B * z2 * z) % P,
            ((1 - beta) ** 2 * x2 * z) % P)


def xz_double(pair):
    x, z = pair
    x2 = x * x % P
    z2 = z * z % P
    z3 = z2 * z % P
    x3 = x2 * x % P
    return ((x2 * x2 - 8 * B * x * z3) % P,
            (4 * z * (x3 + B * z3)) % P)


def xz_dadd(left, right, difference):
    x2, z2 = left
    x3, z3 = right
    x1, z1 = difference
    a = x2 * x3 % P
    b = z2 * z3 % P
    c = x2 * z3 % P
    d = x3 * z2 % P
    return (z1 * (a * a - 4 * B * b * (c + d)) % P,
            x1 * (c - d) ** 2 % P)


def main():
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    beta = int(fixture["beta_hex"], 16)
    assert beta not in (0, 1) and pow(beta, 3, P) == 1
    checks = {"tau": 0, "double": 0, "differential_add": 0}
    scales = (1, 2, 3, 7)
    for case in fixture["cases"]:
        base = (int(case["base_x_hex"], 16), int(case["base_y_hex"], 16))
        assert base[1] * base[1] % P == (pow(base[0], 3, P) + B) % P
        twice = affine_add(base, base)
        thrice = affine_add(twice, base)
        assert twice is not None and thrice is not None
        omega_base = (beta * base[0] % P, base[1])
        omega_twice = (beta * twice[0] % P, twice[1])
        tau_base = affine_add(base, (omega_base[0], -omega_base[1] % P))
        tau_twice = affine_add(twice, (omega_twice[0], -omega_twice[1] % P))
        assert tau_base is not None and tau_twice is not None
        for scale in scales:
            base_xz = (base[0] * scale % P, scale)
            twice_xz = (twice[0] * scale % P, scale)
            assert xz_affine(xz_tau(base_xz, beta)) == tau_base[0]
            assert xz_affine(xz_tau(twice_xz, beta)) == tau_twice[0]
            checks["tau"] += 2
            assert xz_affine(xz_double(base_xz)) == twice[0]
            checks["double"] += 1
            # P + 2P = 3P, with known difference P.
            difference_xz = (base[0] * (scale + 1) % P, scale + 1)
            assert xz_affine(xz_dadd(base_xz, twice_xz, difference_xz)) == thrice[0]
            checks["differential_add"] += 1
    assert len(fixture["cases"]) == 64
    result = {
        "schema": 1,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": 64,
        "projective_scales": list(scales),
        "exact_x_checks": checks,
        "generic_source_counts": {
            "xz_tau": "4M+2S (b=7 constant by additions)",
            "jacobian_tau": "4M+2S",
            "xz_double": "4M+3S (EFD alternative)",
            "jacobian_double": "2M+5S",
            "xz_dadd_affine_difference": "6M+2S after common-subexpression reuse, b=7 constant by additions",
            "xz_dadd_general_difference": "7M+2S after common-subexpression reuse, b=7 constant by additions",
            "jacobian_mixed_add": "8M+3S",
        },
        "decision": "the x-only tau map ties the Jacobian primitive, while differential addition is cheaper with an affine known difference; a complete chain must charge maintenance of that difference and y recovery",
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
