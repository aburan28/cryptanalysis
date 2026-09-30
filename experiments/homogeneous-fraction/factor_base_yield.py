#!/usr/bin/env python3
"""Audit fraction bases and subgroup projections for the n=13/53/83 sweep.

This is a base-validity and tuple-count screen. The tuple ratio is only an
upper bound; ordinary-target yield is measured separately by the compiled
collector. The exact field, curve, points, hashes, and primality checks are
retained in the JSON result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "pdp-degree-heuristics"))
sys.path.insert(0, str(REPO / "experiments" / "pdp-scaling"))
sys.path.insert(0, str(HERE))

import kernel  # type: ignore  # noqa: E402
from math_model import GF2n  # noqa: E402

MODULI = {
    13: 0x2027,
    53: (1 << 53) | (1 << 6) | (1 << 2) | (1 << 1) | 1,
    83: (1 << 83) | (1 << 45) | (1 << 2) | (1 << 1) | 1,
}
CURVE_ORDER_FACTORS = {
    13: (4, 2003),
    53: (428, 21044858204113),
    83: (4, 2417851639230796216685689),
}
MR64_BASES = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
INF = (kernel.INF_X, 0)


class PythonCurveField:
    """Pure-Python fallback for n=83, above the C kernel's 64-bit limit."""

    def __init__(self, n: int, modulus: int):
        self.n = n
        self.F = GF2n(n, modulus)

    def mul(self, a: int, b: int) -> int:
        return self.F.mul(a, b)

    def sqr(self, a: int) -> int:
        return self.F.sq(a)

    def pow(self, a: int, e: int) -> int:
        return self.F.power(a, e)

    def inv(self, a: int) -> int:
        return self.F.inv(a)

    def trace(self, a: int) -> int:
        total, x = 0, a
        for _ in range(self.n):
            total ^= x
            x = self.F.sq(x)
        assert total in (0, 1)
        return total

    def half_trace(self, a: int) -> int:
        total, x = 0, a
        for _ in range((self.n + 1) // 2):
            total ^= x
            x = self.F.sq(self.F.sq(x))
        return total

    def add(self, p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
        if p[0] == kernel.INF_X:
            return q
        if q[0] == kernel.INF_X:
            return p
        result = self.F.add(p, q)
        return INF if result is None else result

    def smul(self, p: tuple[int, int], k: int) -> tuple[int, int]:
        return scalar_mul(self, p, k)

    def lift_batch(self, xs: np.ndarray) -> tuple[list[int], list[bool]]:
        ys, valid = [], []
        for x in map(int, xs):
            if x == 0:
                ys.append(1)
                valid.append(True)
                continue
            rhs = x ^ self.F.inv(self.F.sq(x))
            if self.trace(rhs):
                ys.append(0)
                valid.append(False)
                continue
            y = self.F.mul(x, self.half_trace(rhs))
            ys.append(y)
            valid.append(True)
        return ys, valid

    def on_curve(self, p: tuple[int, int]) -> bool:
        if p[0] == kernel.INF_X:
            return True
        x, y = p
        return self.F.sq(y) ^ self.F.mul(x, y) == self.F.mul(self.F.sq(x), x) ^ 1


def make_field(n: int):
    if n <= 63:
        return kernel.Field(n, MODULI[n], 0, 1)
    return PythonCurveField(n, MODULI[n])


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def koblitz_order(n: int) -> int:
    """#E(F_2^n) for y^2+xy=x^3+1, from tau^2+tau+2=0."""
    t0, t1 = 2, -1
    for _ in range(n - 1):
        t0, t1 = t1, -t1 - 2 * t0
    return (1 << n) + 1 - t1


def poly_rem(a: int, b: int) -> int:
    while a and a.bit_length() >= b.bit_length():
        a ^= b << (a.bit_length() - b.bit_length())
    return a


def poly_gcd(a: int, b: int) -> int:
    while b:
        a, b = b, poly_rem(a, b)
    return a


def irreducible(n: int, modulus: int, field: kernel.Field) -> bool:
    """Rabin irreducibility test over F_2."""
    degree_primes = []
    q = n
    p = 2
    while p * p <= q:
        if q % p == 0:
            degree_primes.append(p)
            while q % p == 0:
                q //= p
        p += 1
    if q > 1:
        degree_primes.append(q)
    checks = {n // p for p in degree_primes}
    xpow = 2
    for i in range(1, n + 1):
        xpow = field.sqr(xpow)
        if i in checks and poly_gcd(xpow ^ 2, modulus) != 1:
            return False
    return xpow == 2


def prime64(n: int) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in MR64_BASES:
        a %= n
        if a in (0, 1):
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def subgroup_prime_certificate(n: int) -> dict:
    r = CURVE_ORDER_FACTORS[n][1]
    if r < 1 << 64:
        assert prime64(r)
        method = "deterministic Miller-Rabin for unsigned 64-bit integers"
        details = {"bases": list(MR64_BASES)}
    else:
        factors = {2: 3, 3: 1, 11: 1, 83: 1, 109: 1,
                   1012327725929069161: 1}
        assert math.prod(q ** e for q, e in factors.items()) == r - 1
        assert all(q < 1 << 64 and prime64(q) for q in factors)
        witnesses = []
        for q in factors:
            witness = next(a for a in range(2, 1000)
                           if pow(a, r - 1, r) == 1
                           and math.gcd(pow(a, (r - 1) // q, r) - 1, r) == 1)
            witnesses.append({"q": q, "a": witness})
        method = "Pocklington using the complete factorization of r-1; "+\
                 "64-bit deterministic Miller-Rabin for its prime factors"
        details = {"r_minus_1_factorization": [[q, e] for q, e in factors.items()],
                   "pocklington_witnesses": witnesses,
                   "64_bit_miller_rabin_bases": list(MR64_BASES)}
    return {"status": "proved", "method": method, **details}


def scalar_mul(field: kernel.Field, point: tuple[int, int], scalar: int) -> tuple[int, int]:
    """Double-and-add without the kernel binding's 64-bit scalar restriction."""
    out = INF
    while scalar:
        if scalar & 1:
            out = field.add(out, point)
        point = field.add(point, point)
        scalar >>= 1
    return out


def negative(point: tuple[int, int]) -> tuple[int, int]:
    return point if point[0] == kernel.INF_X else (point[0], point[0] ^ point[1])


def fraction_abscissae(n: int, k: int, field: kernel.Field) -> list[int]:
    powers = [field.pow(2, j) for j in range(k + 1)]
    xs = set()
    for word in range(1 << (2 * (k + 1))):
        numerator = denominator = 0
        for j, value in enumerate(powers):
            if word & (1 << j):
                numerator ^= value
            if word & (1 << (k + 1 + j)):
                denominator ^= value
        if denominator:
            xs.add(field.mul(numerator, field.inv(denominator)))
    assert all(0 <= x < (1 << n) for x in xs)
    return sorted(xs)


def construct_base(n: int, k: int, field: kernel.Field, h: int, r: int,
                   canonical_generator: tuple[int, int] | None = None) -> dict:
    x_values = fraction_abscissae(n, k, field)
    xs_for_lift = (np.asarray(x_values, dtype=np.uint64) if n <= 63 else x_values)
    ys, ok = field.lift_batch(xs_for_lift)
    original = []
    for x, y, lifts in zip(x_values, map(int, ys), map(bool, ok)):
        if not lifts:
            continue
        points = [(x, y)] + ([(x, x ^ y)] if x else [])
        for point in points:
            assert field.on_curve(point)
            original.append(point)
    original = sorted(set(original))
    projected_map = {p: field.smul(p, h) for p in original}
    projected = sorted(set(projected_map.values()) - {INF})
    for point in projected:
        assert point != INF
        assert scalar_mul(field, point, r) == INF
    if canonical_generator is None:
        generator = projected[0]
    else:
        generator = canonical_generator
        assert generator in projected
    representatives = sorted({min(point, negative(point)) for point in projected})
    assert len(projected) == 2 * len(representatives)
    base = {
        "field_degree": n,
        "field_modulus": hex(MODULI[n]),
        "field_representation": "polynomial_basis; bit i is coefficient of z^i",
        "curve": "y^2+xy=x^3+1 over F_(2^n)",
        "curve_order": str(koblitz_order(n)),
        "cofactor": h,
        "subgroup_order": str(r),
        "fraction_k": k,
        "fraction_space_basis": [1 << j for j in range(k + 1)],
        "fraction_abscissae": x_values,
        "original_points": [list(p) for p in original],
        "projected_nonidentity_points": [list(p) for p in projected],
        "signed_representatives": [list(p) for p in representatives],
        "generator": list(generator),
        "projection": f"P -> [{h}]P",
        "rank_modulus": str(r),
    }
    return {
        "base": base,
        "base_sha256": digest(base),
        "fraction_abscissae_count": len(x_values),
        "original_lifted_points": len(original),
        "projected_nonidentity_points": len(projected),
        "effective_signed_columns": len(representatives),
        "subgroup_membership_checked": True,
        "generator_order_checked": scalar_mul(field, generator, r) == INF,
        "distinct_point_digest": digest({"original": original,
                                          "projected": projected}),
        "ordered_projected_triples_upper_bound_numerator": len(projected) ** 3,
        "ordered_projected_triples_upper_bound_denominator": str(r),
        "uniform_query_coverage_upper_bound_m3": len(projected) ** 3 / r,
    }


def run() -> dict:
    runs = []
    canonical_generators = {}
    for n in (13, 53, 83):
        start = time.perf_counter_ns()
        h, r = CURVE_ORDER_FACTORS[n]
        field = make_field(n)
        irred = irreducible(n, MODULI[n], field)
        order = koblitz_order(n)
        assert irred and order == h * r
        prime_certificate = subgroup_prime_certificate(n)
        for k in (2, 3, 4):
            base_start = time.perf_counter_ns()
            audit = construct_base(n, k, field, h, r,
                                   canonical_generators.get(n))
            if k == 2:
                canonical_generators[n] = tuple(audit["base"]["generator"])
            audit["base_construction_seconds"] = (
                time.perf_counter_ns() - base_start) / 1e9
            audit["factor_base"] = audit.pop("base")
            audit["field_modulus_irreducible"] = irred
            audit["curve_order_formula"] = "Koblitz Lucas recurrence, mu=-1"
            audit["subgroup_order_primality"] = prime_certificate
            audit["coverage_bound_meaning"] = (
                "ordered projected triples divided by r; upper bound only, not measured yield")
            runs.append(audit)
        print(f"n={n} base sweep complete in "
              f"{(time.perf_counter_ns()-start)/1e9:.2f}s", flush=True)
    return {
        "schema": "homogeneous-fraction-factor-base-yield.v1",
        "scope": "base_validity_and_coverage_screen; no homogeneous solver claim",
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "factor_base_yield_results.json")
    args = parser.parse_args()
    result = run()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    for row in result["runs"]:
        base = row["factor_base"]
        print(json.dumps({
            "n": base["field_degree"], "k": base["fraction_k"],
            "x": row["fraction_abscissae_count"],
            "original": row["original_lifted_points"],
            "projected": row["projected_nonidentity_points"],
            "columns": row["effective_signed_columns"],
            "m3_upper": row["uniform_query_coverage_upper_bound_m3"],
        }))


if __name__ == "__main__":
    main()
