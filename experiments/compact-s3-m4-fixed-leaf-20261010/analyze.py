#!/usr/bin/env python3
"""Compare Q1423 formulas and compute a scoped exact N131 rank-supply bound."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
BASELINES = {53: "runs/n53_ordinary_exact_base_orbit.json",
             83: "runs/n83_q1404_ordinary.json"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ceil_div(a, b):
    return (a + b - 1) // b


def main():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert json.loads((HERE / "verification.json").read_text())["status"] == "PASS"
    comparison = {}
    for n in (53, 83):
        baseline_path = OLD / BASELINES[n]
        baseline = json.loads(baseline_path.read_text())
        current = json.loads((HERE / f"n{n}_pool1.json").read_text())
        assert (baseline["factor_base_actual_B"],
                baseline["factor_base_folded_columns"],
                baseline["factor_base_enumerated_set_sha256"]) == (
            current["factor_base_actual_B"],
            current["factor_base_folded_columns_K"],
            current["factor_base_enumerated_set_sha256"])
        old = baseline["formula"]
        new = current["formula"]
        comparison[str(n)] = {
            "curve_id": current["curve_id"],
            "ordinary_workload_id": current["workload_id"],
            "baseline_receipt": BASELINES[n],
            "baseline_receipt_sha256": sha(baseline_path),
            "formula_variables_before": old["variables"],
            "formula_variables_after": new["variables"],
            "variable_reduction_percent": 100 * (1 - new["variables"] / old["variables"]),
            "and_gates_before": old["and_gates"],
            "and_gates_after": new["and_gates"],
            "and_gate_reduction_percent": 100 * (1 - new["and_gates"] / old["and_gates"]),
            "ordinary_run_statuses": {
                mode: json.loads((HERE / f"n{n}_{mode}.json").read_text())["solver"]["status"]
                for mode in ("pool1", "pool64")},
            "status_interpretation": "bounded searches; no natural-yield estimate",
        }
    protocol_path = OLD / "q1413_projected_x_protocol.json"
    base_path = OLD / "runs/n131_q1413_projected_x_w6.json"
    protocol = json.loads(protocol_path.read_text())
    base = json.loads(base_path.read_text())
    r = int(protocol["instances"]["131"]["subgroup_order"])
    B = base["actual_usable_points_B_before_folding"]
    K = base["signed_frobenius_columns_K"]
    assert base["curve_id"] == protocol["instances"]["131"]["curve_id"]
    assert base["curve_id"] == "EC1N131Ckb1h6816f880945e"
    assert B == 6559634788 and K == 25036774
    unordered = math.comb(B + 2, 3)
    # Q is uniform among the r-1 nonidentity subgroup points; one fixed base
    # point must be selected independently of Q. Each multiset maps to one Q.
    mean_upper = unordered / (r - 1)
    queries_50 = ceil_div(K * (r - 1), 2 * unordered)
    queries_expected_k = ceil_div(K * (r - 1), unordered)
    four_sum_path = OLD / "runs/n131_q1414_exact_uniform_query_bound.json"
    four_sum = json.loads(four_sum_path.read_text())
    assert four_sum["curve_id"] == base["curve_id"]
    assert four_sum["actual_usable_points_B_before_folding"] == B
    assert four_sum["folded_columns_K"] == K
    four_sum_50_log2 = four_sum["query_bounds"]["rank_success_50_percent"][
        "minimum_queries_log2"]
    result = {
        "schema": "q1423-comparison-and-fixed-point-bound-v1",
        "proposal_id": "Q1423", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "verification_sha256": sha(HERE / "verification.json"),
        "same_base_formula_comparison": comparison,
        "n131_independent_fixed_point_reference": {
            "curve_id": base["curve_id"], "B": B, "K": K,
            "subgroup_order_r": str(r),
            "unordered_triple_multisets_with_repetition": str(unordered),
            "uniform_nonidentity_query_mean_representations_upper": mean_upper,
            "mean_representations_upper_log2": math.log2(mean_upper),
            "necessary_fixed_point_attempts_for_50pct_rank_supply": queries_50,
            "attempts_for_50pct_log2": math.log2(queries_50),
            "necessary_attempts_for_expected_K_representations": queries_expected_k,
            "attempts_for_expected_K_log2": math.log2(queries_expected_k),
            "zero_other_cost_per_attempt_ceiling_under_2pow61": 2**61 / queries_50,
            "zero_other_cost_per_attempt_ceiling_log2": 61 - math.log2(queries_50),
            "four_summand_uniform_query_50pct_log2": four_sum_50_log2,
            "extra_attempt_bits_vs_four_summand_uniform_reference": (
                math.log2(queries_50) - four_sum_50_log2),
            "proof_scope": ("P3 is fixed independently of a uniform nonidentity "
                            "subgroup query Q; each distinct unordered triple "
                            "with repetition gives at most one relation row for "
                            "Q-P3; all yielded rows are optimistically novel; "
                            "Markov bounds 50-percent rank supply"),
            "q1423_policy_scope": ("Q1423 pool1 and pool64 hash the public Q "
                                   "and pool64 scores x(Q-P3); this reference "
                                   "bound does not apply to those adaptive choices"),
            "base_receipt_sha256": sha(base_path),
            "base_protocol_sha256": sha(protocol_path),
            "four_summand_uniform_reference_sha256": sha(four_sum_path),
        },
        "complete_cold_solve_work_log2": None,
        "complete_online_one_target_work_log2": None,
        "measured_n131_field_operations_per_attempt": None,
        "challenge_status": "no measured complete solve exponent",
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"same_base_formula_comparison": comparison,
                      "n131_reference": result["n131_independent_fixed_point_reference"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
