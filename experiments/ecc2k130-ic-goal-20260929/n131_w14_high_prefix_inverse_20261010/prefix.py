#!/usr/bin/env python3
"""Exact high-coordinate W14 pair inverse for low-bit output fibers."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_polynomial_pair_inverse_20261010"
sys.path.insert(0, str(SOURCE))
import oracle

N = oracle.N
D = oracle.D
FULL = (1 << N) - 1
PRODUCT_DIMENSION = 2*D - 1


def popcount(value):
    return bin(value).count("1")


def invariant_mask(field, free_low_bits, product_basis):
    """Rows unchanged in z² and A(z)*p for every low-bit perturbation."""
    if not 0 <= free_low_bits <= N:
        raise ValueError("invalid low-bit width")
    variable_support = 0
    for j in range(free_low_bits):
        basis = 1 << j
        square = field.mul(basis, basis)
        variable_support |= square
        delta_a = square ^ basis
        for product in product_basis:
            variable_support |= field.mul(delta_a, product)
    return FULL ^ variable_support


def inspect_prefix(candidate, z, free_low_bits, mask, max_nullity=12):
    """Return every usable pair with this prefix when nullity is bounded."""
    field = candidate.field
    low_mask = (1 << free_low_bits) - 1
    prefix = z & (FULL ^ low_mask)
    z2 = field.mul(prefix, prefix)
    az = z2 ^ prefix
    columns = [value & mask for value in candidate.squared_u]
    columns += [field.mul(az, basis) & mask
                for basis in candidate.product_basis]
    assert len(columns) == D + PRODUCT_DIMENSION == 41
    pivots, kernel = oracle.echelon(columns)
    rank = len(pivots)
    particular = oracle.solve(pivots, z2 & mask)
    common = {"free_low_bits": free_low_bits,
              "prefix": prefix, "invariant_rows": popcount(mask),
              "projected_rank": rank, "nullity": len(kernel),
              "coefficient_vectors_tested": 0,
              "fixed_sum_calls": 0, "pre_group_candidate_pairs": 0,
              "pairs": []}
    if particular is None:
        return {**common, "status": "INCONSISTENT_HIGH"}
    if len(kernel) > max_nullity:
        return {**common, "status": "RANK_FALLBACK"}
    matches = set()
    candidates = set()
    tested = fixed_calls = 0
    for code in oracle.affine_solutions(particular, kernel):
        tested += 1
        sum_mask = code & ((1 << D) - 1)
        if sum_mask == 0:
            continue
        product = oracle.coordinate(candidate.product_basis, code >> D)
        fixed_calls += 1
        for pair in candidate.fixed_sum(sum_mask, product):
            candidates.add(pair)
            left_options = candidate.point_options(pair[0])
            right_options = candidate.point_options(pair[1])
            outputs = (candidate.phi_of(candidate.curve.add(left, right))
                       for left in left_options for right in right_options)
            if any(out is not None and (out & (FULL ^ low_mask)) == prefix
                   for out in outputs):
                matches.add(pair)
    return {**common, "status": "COMPLETE_PAIRS" if matches else "COMPLETE_NO_PAIR",
            "coefficient_vectors_tested": tested,
            "fixed_sum_calls": fixed_calls,
            "pre_group_candidate_pairs": len(candidates),
            "pairs": [list(pair) for pair in sorted(matches)]}
