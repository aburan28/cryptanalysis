#!/usr/bin/env python3
"""Bound uniform-target coverage of Q1331's fixed, sampled pair-state set.

This is a counting bound on the frozen search support, not an empirical
relation-yield estimate. It does not assume independent or uniform pair sums.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT = HERE / "runs/n83_q1331_uniform_target_coverage_bound.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def minimum_states_for_coverage(n: int, r: int, numerator: int,
                                denominator: int) -> int:
    """Necessary M for C(4*n*M+1,2)/(r-1) >= numerator/denominator."""
    assert 0 < numerator <= denominator

    def sufficient_counting_capacity(m: int) -> bool:
        pair_points = 4 * n * m
        return (denominator * pair_points * (pair_points + 1)
                >= 2 * numerator * (r - 1))

    low, high = 0, 1
    while not sufficient_counting_capacity(high):
        high *= 2
    while low + 1 < high:
        middle = (low + high) // 2
        if sufficient_counting_capacity(middle):
            high = middle
        else:
            low = middle
    assert high == 1 or not sufficient_counting_capacity(high - 1)
    return high


def build() -> dict:
    base_path = HERE / "q1325_protocol.json"
    stage_path = HERE / "q1330_q1331_batch_root_protocol.json"
    run_path = HERE / "runs/n83_batch_root_capped_2m.json"
    native_path = HERE / "native_s3_root.rs"
    base = json.loads(base_path.read_text())
    stage = json.loads(stage_path.read_text())
    run = json.loads(run_path.read_text())
    profile, = (item for item in stage["profiles"]
                if item["proposal_id"] == "Q1331")

    assert base["proposal_id"] == "Q1325"
    assert run["proposal_id"] == "Q1331"
    assert run["status"] == "state_cap_no_relation"
    assert run["candidate_id"] is None and run["run_id"] is None
    assert base["isogeny"] == stage["isogeny"] == run["isogeny"] == "none"
    assert base["curve"]["curve_id"] == profile["curve_id"] == run["curve_id"]
    assert base["ordinary_workload_id"] == profile["workload_id"] == run["workload_id"]
    assert (base["factor_base"]["enumerated_set_sha256"]
            == profile["factor_base_enumerated_set_sha256"]
            == run["factor_base_enumerated_set_sha256"])
    assert (base["factor_base"]["signed_frobenius_columns"]
            == profile["factor_base_folded_columns_K"] == run["folded_columns_K"])
    assert (base["factor_base"]["actual_usable_points_B_before_folding"]
            == profile["factor_base_actual_B"] == run["actual_usable_points_B"])
    assert stage["native_source_sha256"] == run["native_source_sha256"] == sha(native_path)
    assert run["stage_protocol_sha256"] == sha(stage_path)
    assert profile["index_state_selection"] == run["sampling"]["kind"]
    assert profile["target_orientations_per_state"] == run["sampling"]["orientations_per_state"] == 1
    assert run["index_pair_states_examined"] == run["target_states_scanned"] == profile["pair_state_cap"]
    assert run["target_table_hits"] == 0 and run["relation"] is None

    n = base["field"]["n"]
    r = base["curve"]["subgroup_order"]
    m = run["index_pair_states_examined"]
    k = run["folded_columns_K"]
    assert n == run["field_degree"] == profile["field_degree"] == 83
    assert run["total_quotient_pair_states"] == n * k * k
    assert r > 1 and m <= n * k * k

    # Each pair state names two x coordinates. Each has at most two curve
    # lifts, giving at most four signed pair sums. All n global Frobenius
    # rotations give at most 4*n group points per state. Every accepted
    # four-leaf relation adds two points from this fixed union U. Since the
    # group is abelian, at most |U|(|U|+1)/2 distinct targets can lie in U+U.
    pair_point_cap = 4 * n * m
    target_support_cap = min(r - 1, pair_point_cap * (pair_point_cap + 1) // 2)
    with localcontext() as context:
        context.prec = 35
        probability = Decimal(target_support_cap) / Decimal(r - 1)
        fraction_of_full_index = Decimal(m) / Decimal(n * k * k)
        probability_text = f"{probability:.14E}"
        fraction_text = f"{fraction_of_full_index:.14E}"

    thresholds = {}
    for label, numerator, denominator in (("50_percent", 1, 2),
                                          ("95_percent", 19, 20)):
        necessary_m = minimum_states_for_coverage(n, r, numerator, denominator)
        thresholds[label] = {
            "necessary_pair_state_count": necessary_m,
            "necessary_state_count_log2": math.log2(necessary_m),
            "multiple_of_measured_state_cap": f"{Decimal(necessary_m) / Decimal(m):.10f}",
        }

    return {
        "kind": "fixed_pair_state_uniform_target_support_upper_bound",
        "proposal_id": "Q1331",
        "candidate_id": None,
        "run_id": None,
        "curve_id": run["curve_id"],
        "workload_id": run["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": run["actual_usable_points_B"],
        "factor_base_folded_columns_K": k,
        "factor_base_enumerated_set_sha256": run["factor_base_enumerated_set_sha256"],
        "subgroup_order_r": r,
        "field_degree_n": n,
        "fixed_index_pair_states_M": m,
        "full_quotient_pair_state_count": n * k * k,
        "fraction_of_full_index": fraction_text,
        "pair_group_points_cap_4nM": pair_point_cap,
        "uniform_nonidentity_target_support_cap": target_support_cap,
        "uniform_nonidentity_target_count": r - 1,
        "uniform_target_hit_probability_upper_bound": probability_text,
        "uniform_target_hit_probability_upper_bound_log2": (
            math.log2(target_support_cap) - math.log2(r - 1)),
        "necessary_state_count_thresholds": thresholds,
        "proof": "Each fixed pair state specifies two factor-base x coordinates, at most four signed pair sums, and at most n global Frobenius rotations. Their union U has at most 4*n*M subgroup points. A verified four-leaf target must be in U+U, which contains at most |U|(|U|+1)/2 elements because the group is abelian. Divide by r-1 for a uniformly drawn nonidentity subgroup target.",
        "scope": "Q1331's target-independent fixed pair-state set, and any search restricted to those states even if it tries all orientations and has a perfect collision check; no claim for this one frozen target, target-adaptive state sets, other factor bases, or other solver families",
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "source_sha256": sha(Path(__file__)),
        "q1325_protocol_sha256": sha(base_path),
        "q1330_q1331_protocol_sha256": sha(stage_path),
        "q1331_stage_receipt_sha256": sha(run_path),
        "native_source_sha256": sha(native_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == expected
        print(f"PASS {OUT}")
    else:
        OUT.write_text(expected)
        print(expected)


if __name__ == "__main__":
    main()
