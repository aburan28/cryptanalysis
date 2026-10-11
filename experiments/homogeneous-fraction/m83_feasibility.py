#!/usr/bin/env python3
"""High-fidelity n=83 audit of the tiny rational fraction factor base.

This is a base feasibility check only. It does not solve an n=83 polynomial
system, collect natural relations, or estimate a Gröbner/SAT solve time.
"""

import hashlib
import json
import time
from pathlib import Path

from block_fraction_solver import fraction_pair
from math_model import GF2n

N = 83
MODULUS = (1 << 83) | (1 << 45) | (1 << 2) | (1 << 1) | 1
ORDER = 2417851639230796216685689
COFACTOR = 4
K = 2


def irreducible(field):
    def remainder(a, b):
        while a and a.bit_length() >= b.bit_length():
            a ^= b << (a.bit_length() - b.bit_length())
        return a

    def gcd(a, b):
        while b:
            a, b = b, remainder(a, b)
        return a

    xpow = 2
    for i in range(1, N + 1):
        xpow = field.sq(xpow)
        if i <= N // 2 and gcd(xpow ^ 2, MODULUS) != 1:
            return False
    return xpow == 2


def scalar_mul(field, point, k):
    out = None
    while k:
        if k & 1:
            out = field.add(out, point)
        point = field.add(point, point)
        k >>= 1
    return out


def lift(field, x):
    """Solve z²+z=x+x^-2 by half-trace (n odd), then y=x*z."""
    if x == 0:
        return [(0, 1)]
    rhs = x ^ field.inv(field.sq(x))
    z = 0
    term = rhs
    for _ in range((N + 1) // 2):
        z ^= term
        term = field.sq(field.sq(term))
    if field.sq(z) ^ z != rhs:
        return []
    y = field.mul(x, z)
    points = [(x, y), (x, y ^ x)]
    for px, py in points:
        assert field.sq(py) ^ field.mul(px, py) == (
            field.mul(field.sq(px), px) ^ 1)
    return points


def run():
    start = time.perf_counter()
    field = GF2n(N, MODULUS)
    assert irreducible(field)
    xset = set()
    for word in range(1 << (2 * (K + 1))):
        a, b = fraction_pair(word, K, field)
        if b:
            xset.add(field.mul(a, field.inv(b)))
    points = sorted(point for x in xset for point in lift(field, x))
    images = sorted({scalar_mul(field, point, COFACTOR) for point in points}
                    - {None})
    for point in images:
        assert scalar_mul(field, point, ORDER) is None
        assert point != (0, 1)
    representatives = sorted({min(point, (point[0], point[1] ^ point[0]))
                              for point in images})
    assert len(images) == 2 * len(representatives)
    blob = json.dumps({"field": [N, MODULUS], "curve": [0, 1],
                       "points": images}, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "homogeneous-fraction-m83-base-feasibility.v1",
        "curve": "y^2+xy=x^3+1", "field_degree": N, "modulus": hex(MODULUS),
        "curve_order": str(COFACTOR * ORDER), "cofactor": COFACTOR,
        "subgroup_order": str(ORDER), "fraction_k": K,
        "fraction_abscissae": len(xset), "original_lifted_points": len(points),
        "projected_nonidentity_points": len(images),
        "effective_signed_columns": len(representatives),
        "projected_points_sha256": hashlib.sha256(blob.encode()).hexdigest(),
        "exact_projected_points": images,
        "subgroup_membership_checked": True,
        "modulus_irreducible_checked": True,
        "uniform_query_coverage_upper_bound_m3": len(images) ** 3 / ORDER,
        "uniform_query_coverage_upper_bound_m4": len(images) ** 4 / ORDER,
        "bound": "number of ordered projected tuples divided by subgroup order; "
        "an upper bound, not measured relation yield",
        "wall_seconds": time.perf_counter() - start,
        "natural_relations": None, "independent_rank": None,
        "pdp_solver_seconds": None,
    }


if __name__ == "__main__":
    result = run()
    Path("m83_feasibility.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "field_degree", "projected_nonidentity_points",
        "effective_signed_columns", "uniform_query_coverage_upper_bound_m3",
        "wall_seconds")}))
