#!/usr/bin/env python3
"""A conditional, assumption-light query budget for the N131 m=4 base.

The count uses every unordered four-point multiset, including repeated
points. It bounds uniform-target relation supply without a Poisson model or
any assumption about the distribution of subset sums.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "runs/n131_q1406_uniform_query_bound.json"
PROTOCOL = HERE / "protocol.json"
SAMPLE = HERE / "runs/n131_weight6_stratified_sample.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def scenario(label: str, columns: int, r: int, n: int) -> dict:
    assert 0 < columns and 0 < n and 1 < r
    b = 2 * n * columns
    # This includes tuples with repeated points. A particular 4-multiset
    # supplies at most one factor-base coefficient row for its target sum.
    multiset_count = math.comb(b + 3, 4)
    nonidentity_count = r - 1
    with localcontext() as context:
        context.prec = 45
        supply_upper = str(Decimal(multiset_count) / Decimal(nonidentity_count))
    query_bounds = {}
    for name, numerator, denominator in (
        ("rank_success_50_percent", 1, 2),
        ("rank_success_95_percent", 19, 20),
        ("expected_rank_at_least_K", 1, 1),
    ):
        minimum_queries = ceil_div(
            numerator * columns * nonidentity_count,
            denominator * multiset_count,
        )
        query_bounds[name] = {
            "minimum_uniform_nonidentity_queries": minimum_queries,
            "minimum_queries_log2": math.log2(minimum_queries),
            "zero_other_cost_per_query_ceiling_log2_under_2pow61": (
                61 - math.log2(minimum_queries)),
        }
    return {
        "sample_interval_position": label,
        "conditional_factor_base_B": b,
        "conditional_folded_columns_K": columns,
        "unordered_four_point_multisets_including_repeats": str(multiset_count),
        "nonidentity_subgroup_target_count": str(nonidentity_count),
        "uniform_nonidentity_target_mean_relations_upper_decimal": supply_upper,
        "uniform_nonidentity_target_decomposability_probability_upper_decimal": (
            supply_upper if Decimal(supply_upper) < 1 else "1"),
        "query_bounds": query_bounds,
    }


def build() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    sample = json.loads(SAMPLE.read_text())
    design = protocol["degree_131_design"]
    n = design["field"]["n"]
    r = design["curve"]["subgroup_order"]
    assert n == 131
    assert design["proposal_id"] == sample["proposal_id"] == "Q1303"
    assert sample["curve_id"] == design["curve"]["curve_id"]
    assert design["factor_base"]["normal_basis_weight_bound"] == 6
    assert design["isogeny"] == sample["isogeny"] == "none"
    assert sample["conditional_B_assumptions"]
    low, high = sample["conditional_B_normal_95_percent_interval"]
    point = sample["conditional_B_estimate"]
    assert low < point < high
    columns = {
        "lower_sample_interval": math.floor(low / (2 * n)),
        "point_sample_estimate": round(point / (2 * n)),
        "upper_sample_interval": math.ceil(high / (2 * n)),
    }
    assert columns["lower_sample_interval"] < columns[
        "point_sample_estimate"] < columns["upper_sample_interval"]
    rows = [scenario(label, k, r, n) for label, k in columns.items()]
    return {
        "kind": "q1406_conditional_uniform_query_relation_supply_bound",
        "proposal_id": "Q1406",
        "parent_base_proposal_id": "Q1303",
        "candidate_id": None,
        "run_id": None,
        "curve_id": design["curve"]["curve_id"],
        "isogeny": "none",
        "field_degree_n": n,
        "summands_m": 4,
        "factor_base_policy": "cofactor-projected type-II normal-basis x weight at most six",
        "base_status": "sampled_conditional_not_exact_enumerated",
        "base_point_set_digest": None,
        "assumed_signed_frobenius_orbit_size": 2 * n,
        "conditional_base_assumptions": sample["conditional_B_assumptions"],
        "sample_interval_kind": "normal_approximation_95_percent_statistical_not_hard_bound",
        "scope": (
            "Every relation query has a uniform nonidentity subgroup marginal. "
            "Queries may be correlated; all four-point decompositions may be "
            "returned and every row is optimistically novel. The stated rank "
            "gate requires all K independent rows from these queries, with no "
            "pre-supplied factor-base logs or rows from another collector. "
            "The bound does not apply to a nonuniform guided query law, a "
            "different base, more summands, or another source of rank rows."),
        "proof": (
            "There are C(B+3,4) unordered four-point multisets, including "
            "repeats. Summing their representation counts over all subgroup "
            "targets gives this exact count. Thus a uniform nonidentity "
            "target has at most C(B+3,4)/(r-1) expected representations. "
            "Novel rank is at most representations; linearity of expectation "
            "and Markov's inequality give P(rank >= K) <= "
            "queries*C(B+3,4)/(K*(r-1))."),
        "conditional_scenarios": rows,
        "budget_interpretation": (
            "The per-query 2^x values merely divide an abstract 2^61 total "
            "work cap by a necessary query count after setting setup, matrix, "
            "descent, replay, failed-attempt overhead, and calibration costs "
            "to zero. They are upper ceilings on affordable average query "
            "cost, not measured field-operation costs or a complete solve projection."),
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "input_sha256": {
            str(PROTOCOL.relative_to(ROOT)): sha(PROTOCOL),
            str(SAMPLE.relative_to(ROOT)): sha(SAMPLE),
        },
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    serialized = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        assert OUT.read_text() == serialized
        print("PASS: Q1406 uniform-query bound matches frozen inputs and source")
    else:
        OUT.write_text(serialized)
        print(OUT)


if __name__ == "__main__":
    main()
