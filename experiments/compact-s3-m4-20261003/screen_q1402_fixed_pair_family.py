#!/usr/bin/env python3
"""Count uniform-target support for fixed signed-Frobenius pair schedules.

The result is a necessary query-representative count for this one solver
family. It is independent of pair-sum randomness and does not estimate a
complete DLP cost or constrain target-adaptive/algebraic PDP solvers.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING, localcontext
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT = HERE / "runs/n83_n131_q1402_fixed_pair_family_screen.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_ratio(numerator: int, denominator: int) -> int:
    assert numerator >= 0 and denominator > 0
    return (numerator + denominator - 1) // denominator


def full_pair_descriptor_cap(n: int, folded_columns_k: Decimal) -> int:
    """Generous two-relative-sign, ordered-orbit cap, rounded upward."""
    assert n > 0 and folded_columns_k > 0
    return int((2 * n * folded_columns_k * folded_columns_k).to_integral_value(
        rounding=ROUND_CEILING))


def support(n: int, r: int, table_m: int, query_r: int) -> dict:
    assert n > 0 and r > 1 and table_m >= 0 and query_r >= 0
    # One descriptor fixes a full-point pair. Its global sign and all n
    # Frobenius rotations yield at most 2n subgroup elements on each side.
    table_points = 2 * n * table_m
    query_points = 2 * n * query_r
    numerator_cap = min(r - 1, table_points * query_points)
    with localcontext() as context:
        context.prec = 40
        probability = Decimal(numerator_cap) / Decimal(r - 1)
    return {
        "table_group_points_cap": table_points,
        "query_group_points_cap": query_points,
        "uniform_nonidentity_target_support_numerator_cap": numerator_cap,
        "uniform_nonidentity_target_count": r - 1,
        "uniform_target_support_probability_upper_bound": f"{probability:.15E}",
    }


def necessary_queries(n: int, r: int, table_m: int,
                      success_numerator: int,
                      success_denominator: int) -> int:
    """Necessary R for the counting ceiling to reach the given fraction."""
    assert 0 < success_numerator <= success_denominator
    assert table_m > 0
    return ceil_ratio(success_numerator * (r - 1),
                      success_denominator * 4 * n * n * table_m)


def threshold_rows(n: int, r: int, table_m: int) -> dict:
    return {
        label: {
            "necessary_query_representatives": count,
            "necessary_query_representatives_log2": math.log2(count),
        }
        for label, numerator, denominator in (("one_percent", 1, 100),
                                               ("fifty_percent", 1, 2))
        for count in (necessary_queries(n, r, table_m,
                                         numerator, denominator),)
    }


def build() -> dict:
    q1325_path = HERE / "q1325_protocol.json"
    q1400_path = HERE / "q1400_pair_protocol.json"
    q1400_run_path = HERE / "runs/n83_q1400_pair_comparator.json"
    protocol_path = HERE / "protocol.json"
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    replay_path = HERE / "runs/n131_weight6_sage_independent_replay.json"
    q1325 = json.loads(q1325_path.read_text())
    q1400 = json.loads(q1400_path.read_text())
    ordinary = json.loads(q1400_run_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    sample = json.loads(sample_path.read_text())
    replay = json.loads(replay_path.read_text())

    assert q1325["proposal_id"] == "Q1325"
    assert q1400["proposal_id"] == ordinary["proposal_id"] == "Q1400"
    assert q1400["candidate_id"] is ordinary["candidate_id"] is None
    assert q1400["run_id"] is ordinary["run_id"] is None
    assert q1325["isogeny"] == q1400["isogeny"] == ordinary["isogeny"] == "none"
    assert q1400["curve_id"] == ordinary["curve_id"] == q1325["curve"]["curve_id"]
    assert q1400["workload_id"] == ordinary["workload_id"] == q1325[
        "ordinary_workload_id"]
    assert q1400["factor_base_actual_B"] == ordinary["factor_base_actual_B"]
    assert q1400["factor_base_folded_columns_K"] == ordinary[
        "factor_base_folded_columns_K"] == q1325["factor_base"][
            "signed_frobenius_columns"]
    assert q1400["factor_base_enumerated_set_sha256"] == ordinary[
        "factor_base_enumerated_set_sha256"] == q1325["factor_base"][
            "enumerated_set_sha256"]
    assert ordinary["status"] == "no_exact_hit_at_cap"
    assert ordinary["stage_protocol_sha256"] == sha(q1400_path)
    assert ordinary["native_output"]["exact_hit_keys"] == 0
    n83 = q1325["field"]["n"]
    r83 = q1325["curve"]["subgroup_order"]
    m83 = q1400["point_decomposition"]["table_descriptors"]
    reps83 = q1400["point_decomposition"]["query_representatives"]
    assert n83 == 83 and m83 == ordinary["table_descriptors_charged"]
    assert reps83 == ordinary["native_output"]["query_representatives"]
    measured_support = support(n83, r83, m83, reps83)
    assert measured_support[
        "uniform_nonidentity_target_support_numerator_cap"] == 902955008000000

    design = protocol["degree_131_design"]
    assert design["proposal_id"] == sample["proposal_id"] == "Q1303"
    assert design["candidate_id"] is sample["candidate_id"] is None
    assert design["isogeny"] == sample["isogeny"] == "none"
    assert design["curve"]["curve_id"] == sample["curve_id"]
    assert design["factor_base"][
        "actual_usable_points_B_before_folding"] is None
    assert replay["status"] == "PASS"
    assert replay["sample_receipt_sha256"] == sha(sample_path)
    n131 = design["field"]["n"]
    r131 = design["curve"]["subgroup_order"]
    assert n131 == sample["n"] == 131 and r131 > 1
    assert sample["weight_bound"] == 6
    k_estimate = Decimal(str(sample["conditional_folded_columns_estimate"]))
    lower_b, upper_b = sample["conditional_B_normal_95_percent_interval"]
    k_upper = Decimal(str(upper_b)) / Decimal(2 * n131)
    assert k_estimate < k_upper
    full_m_estimate = full_pair_descriptor_cap(n131, k_estimate)
    full_m_upper_case = full_pair_descriptor_cap(n131, k_upper)
    assert full_m_estimate < full_m_upper_case
    generous_online_query_cap = 1 << 31

    def n131_case(table_m: int) -> dict:
        return {
            "generous_full_table_descriptor_cap_M": table_m,
            "full_table_descriptor_cap_log2": math.log2(table_m),
            "necessary_queries_for_uniform_target_support": threshold_rows(
                n131, r131, table_m),
            "support_ceiling_at_2pow31_query_representatives": support(
                n131, r131, table_m, generous_online_query_cap),
        }

    return {
        "kind": "fixed_signed_frobenius_pair_family_counting_screen",
        "proposal_id": "Q1402",
        "parent_stage_proposal_id": "Q1400",
        "n131_factor_base_proposal_id": "Q1303",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "theorem": "For a target-independent table of M full-point pair descriptors and a target-independent query schedule of R descriptors, each side has at most 2*n global-sign/Frobenius points per descriptor. The four-leaf target support has at most (2*n*M)*(2*n*R) nonidentity subgroup points. Therefore a uniform nonidentity target has support probability at most min(1,4*n^2*M*R/(r-1)).",
        "n83_exact_q1325_measured_rectangle": {
            "curve_id": q1400["curve_id"],
            "workload_id": q1400["workload_id"],
            "actual_usable_points_B": q1400["factor_base_actual_B"],
            "folded_columns_K": q1400["factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": q1400[
                "factor_base_enumerated_set_sha256"],
            "table_descriptors_M": m83,
            "query_representatives_R": reps83,
            "support_ceiling": measured_support,
            "necessary_queries_at_fixed_measured_M": threshold_rows(
                n83, r83, m83),
        },
        "n131_conditional_q1303_full_table": {
            "curve_id": design["curve"]["curve_id"],
            "subgroup_order_r": r131,
            "field_degree_n": n131,
            "exact_factor_base_B": None,
            "exact_factor_base_digest": None,
            "folded_columns_estimate_not_exact": str(k_estimate),
            "upper_95_percent_sample_interval_columns_not_hard_bound": str(
                k_upper),
            "table_cap_rule": "ceil(2*n*K^2), generously allowing both relative signs and ordered orbit pairs; rounded upward from each sampled K value",
            "estimated_K_case": n131_case(full_m_estimate),
            "upper_95_percent_K_case_not_hard_bound": n131_case(
                full_m_upper_case),
            "query_representative_cap_for_screen": generous_online_query_cap,
        },
        "scope": "A counting theorem for fixed target-independent table and query descriptor schedules under a uniformly drawn nonidentity subgroup target. Q1303 base size remains a sampled conditional estimate, so its numerical N131 case is not a hard curve-wide bound. Adaptive target-dependent schedules, algebraic PDP, nonuniform guided queries, and other base policies are outside this theorem.",
        "work_unit_warning": "A query representative is a descriptor, not a calibrated field operation. Comparing its count with an operation budget requires a separately justified conversion; no complete 2^x follows from this screen.",
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "challenge_dispatch_allowed": False,
        "source_sha256": sha(Path(__file__)),
        "q1325_protocol_sha256": sha(q1325_path),
        "q1400_protocol_sha256": sha(q1400_path),
        "q1400_ordinary_stage_sha256": sha(q1400_run_path),
        "n131_protocol_sha256": sha(protocol_path),
        "n131_sample_sha256": sha(sample_path),
        "n131_independent_sample_replay_sha256": sha(replay_path),
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
        assert not OUT.exists(), "refusing to overwrite frozen screen"
        OUT.write_text(expected)
        row = json.loads(expected)["n131_conditional_q1303_full_table"]
        print(json.dumps({
            "estimated_1pct_query_representatives": row["estimated_K_case"][
                "necessary_queries_for_uniform_target_support"][
                    "one_percent"]["necessary_query_representatives"],
            "estimated_50pct_query_representatives": row["estimated_K_case"][
                "necessary_queries_for_uniform_target_support"][
                    "fifty_percent"]["necessary_query_representatives"],
        }))


if __name__ == "__main__":
    main()
