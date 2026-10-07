#!/usr/bin/env python3
"""Exact conditional fixed-window tuple support screen from Q1484 strata."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1484 = PARENT / "q1484_n131_window_base"
Q1481 = PARENT / "q1481_window_orbit_base"
DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
CONTROL = HERE / "n53_direct_window_control.json"
RESULT = HERE / "screen_result.json"
INPUTS = {
    "q1484_r2_receipt": Q1484 / "runs/r2/receipt.json",
    "q1484_protocol": Q1484 / "protocol.json",
    "q1484_archive_audit": Q1484 / "archive_audit_r2.json",
    "q1484_uniform_budget": Q1484 / "uniform_query_budget_r2.json",
    "q1481_n53_receipt": Q1481 / "n53_d14_base.json",
    "q1481_protocol": Q1481 / "protocol.json",
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_fraction(value: Fraction) -> int:
    return (value.numerator + value.denominator - 1) // value.denominator


def incidence_count(receipt: dict, d: int) -> tuple[int, int]:
    strata = receipt["strata"]
    assert [row["span"] for row in strata] == list(range(1, d + 1))
    assert all(row["identity_projection_orbits"] == 0 and
               row["duplicate_projected_orbits"] == 0 for row in strata)
    rational_x = sum(row["rational_x_orbits"] *
                     (d - row["span"] + 1) for row in strata)
    return rational_x, 2 * rational_x


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1495"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert sha(DESIGN) == protocol["design_sha256"]
    assert sha(Path(__file__)) == protocol["screen_source_sha256"]
    for label, path in INPUTS.items():
        assert sha(path) == protocol["input_sha256"][label], label
    receipt = json.loads(INPUTS["q1484_r2_receipt"].read_text())
    base_protocol = json.loads(INPUTS["q1484_protocol"].read_text())
    audit = json.loads(INPUTS["q1484_archive_audit"].read_text())
    budget = json.loads(INPUTS["q1484_uniform_budget"].read_text())
    control = json.loads(CONTROL.read_text())
    assert audit["status"] == control["status"] == "PASS"
    assert audit["full_status_bitmap_count_checked"] is True
    assert receipt["curve_id"] == base_protocol["curve_id"] == (
        design["curve_id"])
    assert receipt["actual_usable_points_B_before_folding"] == (
        design["factor_base_actual_B"])
    assert receipt["signed_frobenius_columns_K"] == (
        design["factor_base_folded_columns_K"])
    assert receipt["enumerated_set_sha256"] == design[
        "factor_base_enumerated_set_sha256"]
    assert budget["base_receipt_sha256"] == sha(INPUTS[
        "q1484_r2_receipt"])
    assert budget["base_audit_sha256"] == sha(INPUTS[
        "q1484_archive_audit"])
    n, d, r = (design["field_degree_n"],
               design["nominal_window_dimension_d"],
               base_protocol["subgroup_order"])
    assert n == 131 and 2 * d < n
    assert r - 1 == int(budget["nonidentity_subgroup_target_count"])
    assert receipt["cofactor"] == base_protocol["cofactor"] == 4
    rational_x, B_window = incidence_count(receipt, d)
    assert B_window <= design["factor_base_actual_B"]
    n53_receipt = json.loads(INPUTS["q1481_n53_receipt"].read_text())
    n53_rational, n53_points = incidence_count(n53_receipt, 14)
    assert n53_rational == control["direct_rational_x_count"]
    assert n53_points == control["direct_usable_point_count"]
    assert control["source_sha256"] == protocol[
        "n53_control_source_sha256"]
    assert control["protocol_sha256"] == sha(PROTOCOL)
    assert control["input_sha256"]["q1481_n53_receipt"] == (
        protocol["input_sha256"]["q1481_n53_receipt"])

    per_tuple_numerator = B_window ** 4
    denominator = r - 1
    assert per_tuple_numerator < denominator
    levels = {}
    for level in design["support_levels_decimal"]:
        required = ceil_fraction(Fraction(level) * Fraction(
            denominator, per_tuple_numerator))
        levels[level] = {
            "minimum_target_independent_oriented_tuples": required,
            "minimum_tuples_log2": math.log2(required),
        }
    K = design["factor_base_folded_columns_K"]
    rank_attempts = ceil_fraction(Fraction(95, 100) * K * Fraction(
        denominator, per_tuple_numerator))
    with localcontext() as context:
        context.prec = 80
        p_decimal = str(Decimal(per_tuple_numerator) / Decimal(denominator))
        zero_other_cost_ceiling = str(Decimal(2 ** 61) /
                                      Decimal(rank_attempts))
    return {
        "kind": "q1495_exact_fixed_window_tuple_support_screen",
        "proposal_id": "Q1495", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": design["curve_id"], "field_degree_n": n,
        "nominal_window_dimension_d": d,
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": K,
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "rational_raw_x_in_one_fixed_window": rational_x,
        "subgroup_usable_points_in_one_fixed_window": B_window,
        "subgroup_order_r": str(r),
        "uniform_nonidentity_target_count": str(denominator),
        "single_oriented_tuple_support_numerator": str(
            per_tuple_numerator),
        "single_oriented_tuple_support_denominator": str(denominator),
        "single_oriented_tuple_support_upper_decimal": p_decimal,
        "single_oriented_tuple_support_upper_log2": (
            math.log2(per_tuple_numerator) - math.log2(denominator)),
        "minimum_tuples_for_support_upper_to_reach": levels,
        "full_rank_95_percent_necessary_tuple_attempts": (
            rank_attempts),
        "full_rank_95_percent_necessary_tuple_attempts_log2": (
            math.log2(rank_attempts)),
        "sub_2pow61_zero_other_cost_average_work_per_attempt_ceiling": (
            zero_other_cost_ceiling),
        "sub_2pow61_zero_other_cost_average_work_per_attempt_ceiling_log2": (
            61 - math.log2(rank_attempts)),
        "ordered_window_tuples_total": n ** 4,
        "relative_window_patterns_total": n ** 3,
        "n53_direct_window_control_sha256": sha(CONTROL),
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "scope": design["claim_boundary"],
        "proof": (
            "Each span-s rational raw-x orbit has exactly d-s+1 rotations "
            "inside a specified length-d window because its long zero gap "
            "is unique. Two distinct nonidentity subgroup points arise per "
            "rational x after the audited cofactor map. Each fixed ordered "
            "four-window tuple has at most B_window^4 ordered quadruples, "
            "each summing to one target. Uniform-target support is at most "
            "B_window^4/(r-1); the union bound gives the fixed-schedule "
            "support thresholds. If each tuple returns at most one verified "
            "relation, expected rank from A scheduled tuple attempts is "
            "at most A*B_window^4/(r-1); Markov requires A at least "
            "ceil(0.95*K*(r-1)/B_window^4) for 95% full-rank probability."),
        "is_complete_solve_projection": False,
        "is_empirical_relation_yield": False,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = snapshot()
    if args.check:
        assert json.loads(RESULT.read_text()) == result
        print("Q1495 fixed-window tuple support screen PASS (archived)")
    else:
        assert not RESULT.exists(), "refusing to replace screen result"
        RESULT.write_text(json.dumps(result, indent=2,
                                     sort_keys=True) + "\n")
        print("Q1495 fixed-window tuple support screen written")


if __name__ == "__main__":
    main()
