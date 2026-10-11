#!/usr/bin/env python3
"""Exact cofactor-class support bound for the N53 weight-two raw S3 search."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from math import comb
from math import gcd
from pathlib import Path
import time

from n53_group import COFACTOR, Curve, Field, N, R, normal_basis

HERE = Path(__file__).resolve().parent
RAW_STAGE = HERE / "runs/n53_scale_v1/fc/receipt.json"
M = 5


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_weight_two(curve, conjugates):
    return sorted(point for i, j in itertools.combinations(range(N), 2)
                  for point in curve.lift(conjugates[i] ^ conjugates[j]))


def cofactor_classes(curve, points):
    """Index [r]P in the cyclic order-428 torsion subgroup."""
    torsion_points = []
    for point in points:
        torsion = curve.mul(point, R)
        assert curve.mul(torsion, COFACTOR) is None
        torsion_points.append(torsion)
    generator = source_point = None
    # The weight-two base itself contains no element of full cofactor order.
    # Find a full-order point outside it to index all 428 possible classes.
    for x in range(1, 10000):
        for point in curve.lift(x):
            torsion = curve.mul(point, R)
            if curve.mul(torsion, COFACTOR // 2) is not None \
                    and curve.mul(torsion, COFACTOR // 107) is not None:
                generator, source_point = torsion, point
                break
        if generator is not None:
            break
    if generator is None:
        raise AssertionError("no order-428 torsion generator found")
    lookup = {}
    current = None
    for i in range(COFACTOR):
        assert current not in lookup
        lookup[current] = i
        current = curve.add(current, generator)
    assert current is None and len(lookup) == COFACTOR
    classes = [lookup[point] for point in torsion_points]
    return generator, source_point, classes


def multiset_torsion_counts(class_counts, m):
    """Coefficient of z^m in product (1-z*e_t)^(-count[t]) in Z[C_428]."""
    rows = [[0] * COFACTOR for _ in range(m + 1)]
    rows[0][0] = 1
    for torsion_class, count in sorted(class_counts.items()):
        options = [1] + [comb(count + k - 1, k) for k in range(1, m + 1)]
        next_rows = [row.copy() for row in rows]
        for degree in range(m):
            for residue, ways in enumerate(rows[degree]):
                if ways == 0:
                    continue
                for k in range(1, m - degree + 1):
                    next_rows[degree + k][(residue + k * torsion_class) % COFACTOR] \
                        += ways * options[k]
        rows = next_rows
    return rows[m]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("coverage receipt is immutable")
    out.mkdir(parents=True)
    start = time.perf_counter_ns()
    stage = json.loads(RAW_STAGE.read_text())
    field = Field()
    curve = Curve(field)
    _, conjugates = normal_basis(field)
    raw = raw_weight_two(curve, conjugates)
    assert len(raw) == stage["factor_base"]["geometric_points"] == 1696
    assert len(set(raw)) == len(raw)
    generator, generator_source, classes = cofactor_classes(curve, raw)
    small = classes[:12]
    small_dp = multiset_torsion_counts(Counter(small), M)
    small_brute = sum(sum(choice) % COFACTOR == 0 for choice in
                      itertools.combinations_with_replacement(small, M))
    assert small_dp[0] == small_brute
    assert sum(small_dp) == comb(len(small) + M - 1, M)
    counts = Counter(classes)
    torsion_multisets = multiset_torsion_counts(counts, M)
    all_multisets = comb(len(raw) + M - 1, M)
    assert sum(torsion_multisets) == all_multisets
    subgroup_multisets = torsion_multisets[0]
    assert 0 < subgroup_multisets < R
    # Every multiset contributes at most one point in the prime subgroup.
    # Thus the exact numerator below is a rigorous support upper bound for
    # a uniform subgroup target, irrespective of prime-component collisions.
    record = {
        "kind": "n53_weight2_five_raw_sum_subgroup_support_bound",
        "curve_id": stage["curve_id"], "candidate_id": None,
        "raw_stage_receipt_sha256": sha(RAW_STAGE),
        "source_sha256": {"audit_n53_raw_coverage.py": sha(Path(__file__)),
                          "n53_group.py": sha(HERE / "n53_group.py")},
        "raw_base_points": len(raw), "summands": M,
        "small_exhaustive_multisets_checked": comb(len(small) + M - 1, M),
        "cofactor": COFACTOR, "subgroup_order": R,
        "torsion_generator": list(generator),
        "torsion_generator_source_point": list(generator_source),
        "torsion_generator_order": COFACTOR,
        "occupied_torsion_classes": len(counts),
        "raw_torsion_order_mix": {str(order): sum(COFACTOR // gcd(k, COFACTOR) == order
                                                 for k in classes)
                                  for order in (1, 2, 4, 107, 214, 428)},
        "torsion_class_counts_sha256": hashlib.sha256(json.dumps(
            [counts.get(i, 0) for i in range(COFACTOR)],
            separators=(",", ":")).encode()).hexdigest(),
        "all_unordered_multisets_with_repetition": all_multisets,
        "multisets_whose_sum_is_in_subgroup": subgroup_multisets,
        "uniform_subgroup_target_support_upper_bound": {
            "numerator": subgroup_multisets, "denominator": R,
            "decimal": format(subgroup_multisets / R, ".12f")},
        "proof": "The [r] map sends each raw point to one of 428 torsion classes. "
                 "Class-count generating-function convolution counts exactly the "
                 "five-point multisets whose torsion sum is zero. Their raw sums "
                 "lie in the order-r subgroup, and each multiset hits at most one "
                 "subgroup target. Divide by r for a uniform subgroup target.",
        "wall_ns": time.perf_counter_ns() - start,
        "claim_boundary": "Rigorous support upper bound across uniform subgroup targets, not an exact hit test for the frozen point, a measured relation yield, or an IC run."}
    (out / "receipt.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: record[key] for key in
                      ("raw_base_points", "occupied_torsion_classes",
                       "all_unordered_multisets_with_repetition",
                       "multisets_whose_sum_is_in_subgroup",
                       "uniform_subgroup_target_support_upper_bound", "wall_ns")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
