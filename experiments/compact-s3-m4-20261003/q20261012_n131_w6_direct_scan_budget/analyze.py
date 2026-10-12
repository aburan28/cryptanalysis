#!/usr/bin/env python3
"""Reprice the paired-sign direct scan on the exact N131 W6 base."""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1413 = PARENT / "runs/n131_q1413_projected_x_w6.json"
Q1414 = PARENT / "runs/n131_q1414_exact_uniform_query_bound.json"
Q1502 = PARENT / "q20261012_n83_signed_pair_batch/analysis.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def freeze():
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    base, supply, kernel = read(Q1413), read(Q1414), read(Q1502)
    assert base["proposal_id"] == "Q1413"
    assert supply["proposal_id"] == "Q1414"
    assert kernel["proposal_id"] == "Q1502"
    assert base["curve_id"] == supply["curve_id"] == protocol["curve_id"]
    assert base["actual_usable_points_B_before_folding"] == supply[
        "actual_usable_points_B_before_folding"]
    assert base["signed_frobenius_columns_K"] == supply["folded_columns_K"]
    assert base["enumerated_set_sha256"] == supply["base_set_sha256"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1504", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "q1413_exact_base_sha256": sha(Q1413),
        "q1414_rank_supply_sha256": sha(Q1414),
        "q1502_kernel_analysis_sha256": sha(Q1502),
        "curve_id": protocol["curve_id"],
        "actual_B": base["actual_usable_points_B_before_folding"],
        "folded_K": base["signed_frobenius_columns_K"],
        "enumerated_set_sha256": base["enumerated_set_sha256"]})
    print("Q1504 frozen", sha(HERE / "freeze.json")[:12])


def analyze():
    assert not (HERE / "analysis.json").exists()
    protocol, frozen = read(HERE / "protocol.json"), read(HERE / "freeze.json")
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    assert sha(Path(__file__)) == frozen["source_sha256"]
    assert sha(Q1413) == frozen["q1413_exact_base_sha256"]
    assert sha(Q1414) == frozen["q1414_rank_supply_sha256"]
    assert sha(Q1502) == frozen["q1502_kernel_analysis_sha256"]
    base, supply, kernel = read(Q1413), read(Q1414), read(Q1502)
    b, k = frozen["actual_B"], frozen["folded_K"]
    assert b == base["actual_usable_points_B_before_folding"] == supply[
        "actual_usable_points_B_before_folding"]
    assert k == base["signed_frobenius_columns_K"] == supply["folded_columns_K"]
    assert b % 2 == 0
    assert kernel["n83_baseline_mul_calls_excluding_inversion_internals"] == 20 * 30977592
    assert kernel["n83_signed_pair_mul_calls_excluding_inversion_internals"] == 14 * 30977592
    batch_pairs = 512
    group_add = 4 * b
    mul_calls = 14 * b
    sqr_calls = group_add
    inversions = 4 * math.ceil((b // 2) / batch_pairs)
    scenarios = {}
    for name, bound in supply["query_bounds"].items():
        queries = bound["minimum_uniform_nonidentity_queries"]
        assert queries > 0
        calls = queries * mul_calls
        scenarios[name] = {
            "necessary_uniform_query_count_from_q1414": queries,
            "necessary_query_count_log2": math.log2(queries),
            "zero_other_per_query_ceiling_log2":
                bound["zero_other_cost_per_query_ceiling_log2_under_2pow61"],
            "one_full_scan_per_query_batch_mul_calls": calls,
            "one_full_scan_per_query_batch_mul_calls_log2": math.log2(calls),
            "gap_above_2pow61_batch_mul_call_bits":
                math.log2(calls) - protocol["challenge_reference_log2"],
            "single_full_scan_vs_zero_other_query_ceiling_bits":
                math.log2(mul_calls) - bound[
                    "zero_other_cost_per_query_ceiling_log2_under_2pow61"],
        }
    output = {
        "proposal_id": "Q1504", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "base_status": "exact enumerated N131 W<=6 projected base",
        "actual_usable_points_B_before_folding": b,
        "folded_columns_K": k,
        "enumerated_set_sha256": frozen["enumerated_set_sha256"],
        "one_full_scan_group_add_attempts": group_add,
        "one_full_scan_group_add_attempts_log2": math.log2(group_add),
        "one_full_scan_batch_mul_calls_excluding_inversion_internals": mul_calls,
        "one_full_scan_batch_mul_calls_log2": math.log2(mul_calls),
        "one_full_scan_batch_sqr_calls_excluding_inversion_internals": sqr_calls,
        "one_full_scan_batch_inversions": inversions,
        "q1502_field_mul_call_reduction_log2_bits":
            kernel["n83_field_mul_call_reduction_log2_bits"],
        "uniform_query_scenarios": scenarios,
        "scope": "Arithmetic scenario for the direct-scan kernel on the exact W6 base, using Q1414 necessary query counts. Each query is charged one complete four-sign scan. It does not cover early stopping, multiple first pairs, guided nonuniform queries, setup, LA, target descent, or replay.",
        "complete_n131_solve_work_log2": None,
        "challenge_dispatch_allowed": False}
    save(HERE / "analysis.json", output)
    print("Q1504 expected-rank scenario", scenarios[
        "expected_rank_at_least_K"]["one_full_scan_per_query_batch_mul_calls_log2"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "analyze"):
        raise SystemExit("usage: analyze.py {freeze|analyze}")
    globals()[sys.argv[1]]()
