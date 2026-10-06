#!/usr/bin/env python3
"""Uniform-query relation-supply bound for Q1303's exact W<=6 base.

This bound is conditional on the collector's uniform nonidentity marginal,
not on a Poisson or independent-subset-sum model. It supplies no PDP cost.
"""

from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

from run_probe import HERE, sha

OUT = HERE / "runs/n131_q1414_exact_uniform_query_bound.json"
BASE = HERE / "runs/n131_q1413_projected_x_w6.json"
BASE_PROTOCOL = HERE / "q1413_projected_x_protocol.json"
PARENT = HERE / "protocol.json"


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def build() -> dict:
    base = json.loads(BASE.read_text())
    protocol = json.loads(BASE_PROTOCOL.read_text())
    parent = json.loads(PARENT.read_text())["degree_131_design"]
    n = base["field_degree_n"]
    b = base["actual_usable_points_B_before_folding"]
    k = base["signed_frobenius_columns_K"]
    r = parent["curve"]["subgroup_order"]
    assert n == 131 and b == 2 * n * k and k > 0
    assert base["proposal_id"] == protocol["proposal_id"] == "Q1413"
    assert base["parent_base_proposal_id"] == parent["proposal_id"] == "Q1303"
    assert base["curve_id"] == parent["curve"]["curve_id"]
    assert base["normal_basis_weight_bound"] == 6
    assert base["isogeny"] == parent["isogeny"] == "none"
    assert base["n83_reference_set_equal"] is False
    assert base["protocol_sha256"] == sha(BASE_PROTOCOL)
    assert protocol["parent_protocol_sha256"] == sha(PARENT)
    assert parent["curve"]["order"] == 4 * r
    multisets = math.comb(b + 3, 4)
    with localcontext() as context:
        context.prec = 50
        mean = Decimal(multisets) / Decimal(r - 1)
    assert mean < 1
    bounds = {}
    for label, num, den in (
        ("rank_success_50_percent", 1, 2),
        ("rank_success_95_percent", 19, 20),
        ("expected_rank_at_least_K", 1, 1),
    ):
        minimum = ceil_div(num * k * (r - 1), den * multisets)
        bounds[label] = {
            "minimum_uniform_nonidentity_queries": minimum,
            "minimum_queries_log2": math.log2(minimum),
            "zero_other_cost_per_query_ceiling_log2_under_2pow61": (
                61 - math.log2(minimum)),
        }
    return {
        "kind": "q1414_exact_base_uniform_query_relation_supply_bound",
        "proposal_id": "Q1414",
        "parent_base_proposal_id": "Q1303",
        "candidate_id": None, "run_id": None,
        "curve_id": base["curve_id"], "isogeny": "none",
        "field_degree_n": n, "summands_m": 4,
        "normal_basis_weight_bound": 6,
        "base_status": "exact_enumerated_projected_x_orbit_set",
        "actual_usable_points_B_before_folding": b,
        "folded_columns_K": k,
        "base_set_encoding": base["enumerated_set_encoding"],
        "base_set_sha256": base["enumerated_set_sha256"],
        "unordered_four_point_multisets_including_repeats": str(multisets),
        "nonidentity_subgroup_target_count": str(r - 1),
        "uniform_nonidentity_target_mean_relations_upper_decimal": str(mean),
        "uniform_nonidentity_target_decomposability_probability_upper_decimal": (
            str(mean)),
        "query_bounds": bounds,
        "scope": (
            "Every relation query has a uniform nonidentity subgroup marginal. "
            "Queries may be correlated; every decomposition may be returned "
            "and every row is optimistically novel. All K independent rows "
            "come from these queries, with no pre-supplied logs or other "
            "collector. A guided nonuniform law is outside this bound."),
        "proof": (
            "At most C(B+3,4) unordered four-point multisets, including "
            "repeats, have a subgroup sum. A uniform nonidentity target has "
            "at most C(B+3,4)/(r-1) expected representations. Novel rank "
            "is no greater than representations; linearity of expectation "
            "and Markov give P(rank >= K) <= "
            "queries*C(B+3,4)/(K*(r-1))."),
        "budget_interpretation": (
            "The 2^x per-query figures are necessary affordability ceilings "
            "in abstract work units with all other costs set to zero. They "
            "are neither measured solver costs nor a complete solve exponent."),
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "base_receipt_sha256": sha(BASE),
        "base_protocol_sha256": sha(BASE_PROTOCOL),
        "parent_protocol_sha256": sha(PARENT),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    serialized = json.dumps(build(), indent=2) + "\n"
    if args.check:
        assert OUT.read_text() == serialized
        print("PASS: Q1414 exact-base uniform-query bound")
    else:
        assert not OUT.exists()
        OUT.write_text(serialized)
        print(OUT)


if __name__ == "__main__":
    main()
