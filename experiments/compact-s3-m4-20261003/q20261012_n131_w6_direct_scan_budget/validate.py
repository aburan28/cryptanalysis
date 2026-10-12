#!/usr/bin/env python3
"""Read-only archive check for the exact W6 direct-scan arithmetic record."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "runs/n131_q1413_projected_x_w6.json"
SUPPLY = PARENT / "runs/n131_q1414_exact_uniform_query_bound.json"
KERNEL = PARENT / "q20261012_n83_signed_pair_batch/analysis.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    frozen, protocol, result = (read(HERE / n) for n in
                                ("freeze.json", "protocol.json", "analysis.json"))
    base, supply, kernel = read(BASE), read(SUPPLY), read(KERNEL)
    assert frozen["source_sha256"] == sha(HERE / "analyze.py")
    assert frozen["protocol_sha256"] == sha(HERE / "protocol.json")
    assert frozen["q1413_exact_base_sha256"] == sha(BASE)
    assert frozen["q1414_rank_supply_sha256"] == sha(SUPPLY)
    assert frozen["q1502_kernel_analysis_sha256"] == sha(KERNEL)
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["proposal_id"] == protocol["proposal_id"] == "Q1504"
    assert result["candidate_id"] is None and result["run_id"] is None
    assert result["complete_n131_solve_work_log2"] is None
    assert result["challenge_dispatch_allowed"] is False
    assert result["curve_id"] == base["curve_id"] == supply["curve_id"]
    assert result["isogeny"] == "none"
    assert result["enumerated_set_sha256"] == base["enumerated_set_sha256"] == supply[
        "base_set_sha256"]
    b = base["actual_usable_points_B_before_folding"]
    k = base["signed_frobenius_columns_K"]
    assert b == supply["actual_usable_points_B_before_folding"]
    assert k == supply["folded_columns_K"]
    assert (b, k) == (6559634788, 25036774)
    assert result["one_full_scan_group_add_attempts"] == 4 * b
    assert result["one_full_scan_batch_mul_calls_excluding_inversion_internals"] == 14 * b
    assert result["one_full_scan_batch_sqr_calls_excluding_inversion_internals"] == 4 * b
    assert result["one_full_scan_batch_inversions"] == 4 * math.ceil(b / 1024)
    assert kernel["n83_field_mul_call_reduction_fraction"] == 0.3
    for name, bound in supply["query_bounds"].items():
        row = result["uniform_query_scenarios"][name]
        q = bound["minimum_uniform_nonidentity_queries"]
        assert row["necessary_uniform_query_count_from_q1414"] == q
        assert row["one_full_scan_per_query_batch_mul_calls"] == q * 14 * b
        assert math.isclose(row["one_full_scan_per_query_batch_mul_calls_log2"],
                            math.log2(q * 14 * b), abs_tol=1e-12)
        assert math.isclose(row["gap_above_2pow61_batch_mul_call_bits"],
                            math.log2(q * 14 * b) - 61, abs_tol=1e-12)
    print("PASS Q1504 exact W6 direct-scan budget")


if __name__ == "__main__":
    main()
