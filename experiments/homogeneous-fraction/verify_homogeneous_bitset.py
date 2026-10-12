#!/usr/bin/env python3
"""Verify packed GF(2) products, graded ordering, and component ranks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from block_fraction_solver import MODULI, multiplied  # noqa: E402
from homogeneous_bitset import (  # noqa: E402
    MonomialDegreeOrder, bits_to_sparse, degree_one_layer, multiply_variable,
    sparse_to_bits,
)
from math_model import FastGF2n, GF2n  # noqa: E402


def sparse_rank(rows: list[set[int]]) -> int:
    pivots: dict[int, set[int]] = {}
    for row in rows:
        row = set(row)
        while row:
            lead = max(row, key=lambda mon: (mon.bit_count(), mon))
            prior = pivots.get(lead)
            if prior is None:
                pivots[lead] = row
                break
            row.symmetric_difference_update(prior)
    return len(pivots)


def in_sparse_span(poly: set[int], rows: list[set[int]]) -> bool:
    pivots: dict[int, set[int]] = {}
    for source in rows:
        row = set(source)
        while row:
            lead = max(row, key=lambda mon: (mon.bit_count(), mon))
            prior = pivots.get(lead)
            if prior is None:
                pivots[lead] = row
                break
            row.symmetric_difference_update(prior)
    residual = set(poly)
    while residual:
        lead = max(residual, key=lambda mon: (mon.bit_count(), mon))
        prior = pivots.get(lead)
        if prior is None:
            return False
        residual.symmetric_difference_update(prior)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "homogeneous_bitset_verification.json")
    args = parser.parse_args()
    started = time.perf_counter()
    checks = []

    for n, modulus in ((5, MODULI[5]), (7, MODULI[7]),
                       (13, MODULI[13]), (17, 0x20009)):
        slow, fast = GF2n(n, modulus), FastGF2n(n, modulus)
        rng = random.Random(7123 + n)
        for _ in range(20000):
            a, b = rng.randrange(1 << n), rng.randrange(1 << n)
            assert fast.mul(a, b) == slow.mul(a, b)
            assert fast.sq(a) == slow.sq(a)
        checks.append({"check": "fast_field_multiplication", "n": n,
                       "random_pairs": 20000, "status": "PASS"})

    c_source = HERE / "monomial_degree_order.c"
    small_order = MonomialDegreeOrder(8, c_source)
    expected = sorted(range(1 << 8), key=lambda mon: (mon.bit_count(), mon))
    assert all(small_order.rank(mon) == rank
               and small_order.monomial(rank) == mon
               for rank, mon in enumerate(expected))
    checks.append({"check": "small_degree_then_mask_permutation",
                   "all_monomials": 256, "status": "PASS"})

    width, nvars = 2, 6
    order = MonomialDegreeOrder(nvars, c_source)
    for poly_seed in range(64):
        rng = random.Random(3000 + poly_seed)
        poly = {mon for mon in range(1 << nvars) if rng.randrange(2)}
        packed = sparse_to_bits(poly, nvars)
        assert bits_to_sparse(packed) == poly
        for variable in range(nvars):
            product = multiply_variable(packed, variable, nvars)
            assert bits_to_sparse(product) == multiplied(poly, 1 << variable)
        ranked = small_order.reorder(sparse_to_bits(poly, 8))
        ranked_support = bits_to_sparse(ranked)
        assert {small_order.monomial(rank) for rank in ranked_support} == poly
    checks.append({"check": "packed_boolean_multiplication_and_reorder",
                   "polynomials": 64, "variables": nvars, "status": "PASS"})

    rng = random.Random(88124)
    order24 = MonomialDegreeOrder(24, c_source)
    for monomial in [rng.randrange(1 << 24) for _ in range(500)]:
        weight = monomial.bit_count()
        expected_rank = sum(math.comb(24, degree) for degree in range(weight))
        position = 1
        remaining = monomial
        while remaining:
            bit = (remaining & -remaining).bit_length() - 1
            expected_rank += math.comb(bit, position)
            position += 1
            remaining &= remaining - 1
        assert order24.rank(monomial) == expected_rank
        assert order24.monomial(expected_rank) == monomial
    checks.append({"check": "24_variable_rank_and_inverse",
                   "random_monomials": 500, "status": "PASS"})

    equations = [{0, 1, 3, 7, 12}, {1, 2, 7, 15}, {0, 2, 4, 8, 16}]
    base_degree = (1, 1, 1)
    deductions, stats = degree_one_layer(
        equations, width, base_degree, deduction_degree=3, degree_order=order)
    reference_components = [(base_degree, equations)]
    for block in range(3):
        profile = tuple(d + (i == block) for i, d in enumerate(base_degree))
        rows = [multiplied(poly, 1 << (block * width + offset))
                for poly in equations for offset in range(width)]
        reference_components.append((profile, rows))
    assert len(stats["component_matrices"]) == len(reference_components)
    for matrix, (profile, rows) in zip(stats["component_matrices"], reference_components):
        assert matrix["degree"] == list(profile)
        assert matrix["rows"] == len(rows)
        assert matrix["rank"] == sparse_rank(rows)
    assert deductions
    assert all(any(in_sparse_span(poly, rows) for _, rows in reference_components)
               for poly in deductions)
    checks.append({"check": "homogeneous_component_ranks_and_consequences",
                   "profiles": [matrix["degree"] for matrix in stats["component_matrices"]],
                   "rows": stats["rows"], "rank": stats["rank"],
                   "deductions": len(deductions), "status": "PASS"})

    sources = ["math_model.py", "homogeneous_bitset.py",
               "monomial_degree_order.c", "probe_k3_homogeneous_bitset.py",
               "probe_k3_homogeneous_targetonly.py"]
    result = {
        "schema": "homogeneous-fraction-bitset-verification.v1",
        "status": "PASS",
        "checks": checks,
        "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                          for name in sources},
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.out = args.out.resolve()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checks": len(checks),
                      "out": str(args.out)}), flush=True)


if __name__ == "__main__":
    main()
