#!/usr/bin/env python3
"""Source-bound geometry screen for a compact five-summand S3 chain.

This is a design screen. It constructs formula shapes but runs no solver and
does not infer natural relation yield from a planted or timed-out query.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from chain_s3 import Formula, field, multiplication_table, square_destinations
from chain_s3_factored import s3_link_factored
from chain_s3_multitarget import choose_target_x
from run_probe import HERE, ROOT, sha


OUT = HERE / "runs/n83_n131_q1405_m5_chain_screen.json"
SOURCE_PATHS = (
    "experiments/compact-s3-m4-20261003/screen_q1405_m5_chain.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "ecc2k130/codegen/field.py",
)


def shape(n: int, weight: int, target_xs: list[int]) -> dict:
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(5)]
    mids = [[formula.new() for _ in range(n)] for _ in range(3)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, target_xs)
    for a, b, c in zip(
        [leaves[0], *mids],
        [leaves[1], leaves[2], leaves[3], leaves[4]],
        [*mids, target],
    ):
        s3_link_factored(formula, a, b, c, table, square_dest)
    return {
        "summands": 5,
        "s3_links": 4,
        "free_intermediate_x_coordinates": 3,
        "target_selector_bits": len(selector),
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "expanded_s6_materialized": False,
        "solver_attempted": False,
    }


def planning_row(n: int, m: int, b: float, r: int) -> dict:
    k = b / (2 * n)
    log2_mean = sum(math.log2(b - i) for i in range(m)) - (
        math.log2(math.factorial(m)) + math.log2(r))
    mean = 2**log2_mean
    poisson_hit = -math.expm1(-mean)
    ideal_queries = k / poisson_hit
    return {
        "conditional_B": b,
        "conditional_folded_columns_K": k,
        "uniform_target_mean_distinct_subsets": mean,
        "uniform_target_mean_log2": log2_mean,
        "poisson_hit_probability_heuristic": poisson_hit,
        "optimistic_queries_one_novel_row_per_hit": ideal_queries,
        "optimistic_queries_log2": math.log2(ideal_queries),
        "zero_other_cost_per_query_ceiling_log2_under_2pow61": (
            61 - math.log2(ideal_queries)),
    }


def build() -> dict:
    protocol_path = HERE / "protocol.json"
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    ordinary_path = HERE / "runs/n83_q1404_ordinary.json"
    base_path = HERE / "bases/n83_weight4_orbits.json.gz"
    protocol = json.loads(protocol_path.read_text())
    sample = json.loads(sample_path.read_text())
    ordinary = json.loads(ordinary_path.read_text())
    n83 = next(p for p in protocol["profiles"] if p["field"]["n"] == 83)
    n131 = protocol["degree_131_design"]
    assert n83["proposal_id"] == "Q1302"
    assert n83["factor_base"]["normal_basis_weight_bound"] == 4
    assert n83["factor_base"]["actual_usable_points_B_before_folding"] == 1_934_066
    assert n83["factor_base"]["signed_frobenius_columns"] == 11_651
    assert n83["factor_base_archive_sha256"] == sha(base_path)
    assert sample["proposal_id"] == "Q1303"
    assert sample["curve_id"] == n131["curve"]["curve_id"]
    assert ordinary["proposal_id"] == "Q1404"
    assert ordinary["curve_id"] == n83["curve"]["curve_id"]
    assert ordinary["workload_id"] == n83["ordinary_workload_id"]
    assert ordinary["observed_verified_relation_count"] == 0
    assert len(ordinary["raw_preimage_x_coordinates"]) == 4

    strata = [row for row in sample["strata"] if row["weight"] <= 5]
    assert [row["weight"] for row in strata] == [1, 2, 3, 4, 5]
    rational = sum(row["estimated_rational_x_count"] for row in strata)
    variance = sum(row["estimated_count_variance"] for row in strata)
    # This projection assumes two distinct, usable subgroup points per
    # rational x and no cofactor-projection collisions across the sparse set.
    b5 = 2 * rational
    normal_95_halfwidth = 1.96 * 2 * math.sqrt(variance)
    r131 = n131["curve"]["subgroup_order"]
    b6 = sample["conditional_B_estimate"]
    assert math.isclose(b6, 2 * sum(row["estimated_rational_x_count"]
                                    for row in sample["strata"]))

    b83 = n83["factor_base"]["actual_usable_points_B_before_folding"]
    k83 = n83["factor_base"]["signed_frobenius_columns"]
    n83_geometry = planning_row(83, 5, b83, n83["curve"]["subgroup_order"])
    assert math.isclose(n83_geometry["conditional_folded_columns_K"], k83)
    # The 2^61 challenge threshold is a degree-131 objective, not an N83
    # solver budget. Keep N83 geometry but do not issue a misleading ceiling.
    n83_geometry.pop("zero_other_cost_per_query_ceiling_log2_under_2pow61")
    n83_geometry["conditional_B"] = b83
    n83_geometry["conditional_folded_columns_K"] = k83
    n83_geometry["base_geometry_status"] = "exact_enumerated"
    n83_geometry["curve_id"] = n83["curve"]["curve_id"]
    n83_geometry["factor_base_enumerated_set_sha256"] = n83[
        "factor_base"]["enumerated_set_sha256"]
    n83_geometry["ordinary_workload_id"] = n83["ordinary_workload_id"]
    n83_geometry["formula_shape"] = shape(
        83, 4, ordinary["raw_preimage_x_coordinates"])
    n83_geometry["formula_target_policy"] = (
        "four exact cofactor-four preimages of Q1302/Q1404's shared ordinary public target")

    n131_geometry = planning_row(131, 5, b5, r131)
    n131_geometry.update({
        "curve_id": n131["curve"]["curve_id"],
        "base_geometry_status": "sampled_conditional_not_enumerated",
        "conditional_B_normal_95_percent_interval": [
            b5 - normal_95_halfwidth, b5 + normal_95_halfwidth],
        "conditional_B_assumptions": sample["conditional_B_assumptions"],
        "factor_base_enumerated_set_sha256": None,
        "formula_shape": shape(131, 5, [1, 2, 4, 8]),
        "formula_target_policy": (
            "four distinct placeholder x values for formula shape only; not curve preimages or a solver query"),
    })
    m4_reference = planning_row(131, 4, b6, r131)
    m4_reference["proposal_id"] = "Q1303"
    m4_reference["base_geometry_status"] = "sampled_conditional_not_enumerated"

    return {
        "kind": "q1405_compact_five_summand_geometry_and_formula_screen",
        "proposal_id": "Q1405",
        "point_decomposition_stage_code": "PDP5sat",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "status": "planning_screen_only",
        "n83_exact_weight4_five_summand": n83_geometry,
        "n131_conditional_weight5_five_summand": n131_geometry,
        "n131_conditional_weight6_four_summand_reference": m4_reference,
        "interpretation": (
            "Subset means are uniform-target averages conditional on B; the Poisson hit law, "
            "one-novel-row-per-hit query count, and 2^61 per-query ceiling are optimistic "
            "planning assumptions. Formula shape does not imply solver success. "
            "The n83 m5 versus m4 comparison changes both arity and factor-base policy."),
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "input_sha256": {
            str(path.relative_to(ROOT)): sha(path)
            for path in (protocol_path, sample_path, ordinary_path, base_path)
        },
        "source_sha256": {path: sha(ROOT / path) for path in SOURCE_PATHS},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        assert OUT.read_text() == serialized
        print("PASS: Q1405 five-summand screen matches frozen inputs and sources")
    else:
        OUT.write_text(serialized)
        print(OUT)


if __name__ == "__main__":
    main()
