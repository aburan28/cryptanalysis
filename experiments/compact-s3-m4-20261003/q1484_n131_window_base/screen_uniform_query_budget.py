#!/usr/bin/env python3
"""Necessary N131 per-query ceiling from the exact Q1484 base geometry.

This is a uniform-query rank-supply bound, not a PDP cost or complete solve
projection. It follows Q1414's Markov argument with Q1484's changed base.
"""

from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

from freeze_protocol import HERE, PROTOCOL, sha

RUN = HERE / "runs" / "r1"
OUT = HERE / "uniform_query_budget.json"


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def build() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    audit_path = HERE / "archive_audit.json"
    receipt_path = RUN / "receipt.json"
    audit = json.loads(audit_path.read_text())
    base = json.loads(receipt_path.read_text())
    assert protocol["proposal_id"] == audit["proposal_id"] == (
        base["proposal_id"]) == "Q1484"
    assert audit["status"] == "PASS"
    assert audit["receipt_sha256"] == sha(receipt_path)
    assert audit["protocol_sha256"] == sha(PROTOCOL)
    assert audit["status_bitmap_sha256"] == base[
        "status_bitmap_sha256"]
    assert audit["enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert base["candidate_id"] is base["run_id"] is None
    assert base["isogeny"] == "none"
    b = base["actual_usable_points_B_before_folding"]
    k = base["signed_frobenius_columns_K"]
    r = protocol["subgroup_order"]
    assert b == 262 * k and k > 0 and r > 0
    multiset_count = math.comb(b + 3, 4)
    with localcontext() as context:
        context.prec = 60
        mean = Decimal(multiset_count) / Decimal(r - 1)
    bounds = {}
    for label, numerator, denominator in (
        ("rank_success_50_percent", 1, 2),
        ("rank_success_95_percent", 19, 20),
        ("expected_rank_at_least_K", 1, 1),
    ):
        minimum = ceil_div(numerator * k * (r - 1),
                           denominator * multiset_count)
        minimum = max(1, minimum)
        bounds[label] = {
            "minimum_uniform_nonidentity_queries": minimum,
            "minimum_queries_log2": math.log2(minimum),
            "zero_other_cost_per_query_ceiling_log2_under_2pow61": (
                61 - math.log2(minimum)),
        }
    return {
        "kind": "q1484_exact_window_base_uniform_query_rank_supply_bound",
        "proposal_id": "Q1484", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": protocol["curve_id"],
        "field_degree_n": 131, "summands_m": 4,
        "nominal_window_dimension_d": 27,
        "actual_usable_points_B_before_folding": b,
        "folded_columns_K": k,
        "base_set_sha256": base["enumerated_set_sha256"],
        "unordered_four_point_multisets_including_repeats": str(
            multiset_count),
        "nonidentity_subgroup_target_count": str(r - 1),
        "uniform_nonidentity_target_mean_relations_upper_decimal": str(mean),
        "query_bounds": bounds,
        "scope": (
            "Every relation query has a uniform nonidentity subgroup "
            "marginal. Queries may be correlated; every decomposition may "
            "be returned and every row is optimistically novel. All K "
            "independent rows come from these queries, with no pre-supplied "
            "logs or other collector. A guided nonuniform law is outside "
            "this bound."),
        "proof": (
            "At most C(B+3,4) unordered four-point multisets, including "
            "repeats, have a subgroup sum. A uniform nonidentity target "
            "has at most C(B+3,4)/(r-1) expected representations. Novel "
            "rank cannot exceed representations. Linearity of expectation "
            "and Markov bound the probability of rank K by queries times "
            "the mean divided by K."),
        "budget_interpretation": (
            "These 2^x per-query figures are necessary ceilings in an "
            "abstract charged unit if every other cost is zero. They are "
            "neither measured PDP costs nor a complete-solve exponent."),
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "base_receipt_sha256": sha(receipt_path),
        "base_audit_sha256": sha(audit_path),
        "base_protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    serialized = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check or OUT.exists():
        assert OUT.read_text() == serialized
        print("Q1484 uniform-query budget screen PASS (archived)")
    else:
        OUT.write_text(serialized)
        print("Q1484 uniform-query budget screen PASS")


if __name__ == "__main__":
    main()
