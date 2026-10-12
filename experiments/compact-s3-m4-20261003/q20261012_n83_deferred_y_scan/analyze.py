#!/usr/bin/env python3
"""Exact scan accounting and explicitly conditional N131 work scenarios."""
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol = read(HERE / "protocol.json")
    result = read(HERE / "result.json")
    assert sha(HERE / "protocol.json") == result["protocol_sha256"]
    assert sha(HERE / "native_deferred_y.cpp") == protocol["native_source_sha256"]
    assert len(result["rows"]) == 12
    assert all(r["status"] == "COMPLETE" and
               r["result"]["checksum_hex"] == r["baseline_checksum_hex"] and
               r["result"]["hits"] == r["baseline_hits"] == 0 and
               r["result"]["exceptional_pairs"] == 0 for r in result["rows"])
    b83 = protocol["factor_base_actual_B"]
    assert all(r["result"]["scanned"] == b83 for r in result["rows"])
    # Q1413's exact B and K are frozen in Q1504.
    q1504 = read(PARENT / "q20261012_n131_w6_direct_scan_budget/analysis.json")
    b = q1504["actual_usable_points_B_before_folding"]
    k = q1504["folded_columns_K"]
    assert b == 6559634788 and k == 25036774
    q1447_path = PARENT / "q20261011_weight7_screen/measurement.json"
    subgroup_order = int(read(q1447_path)["subgroup_order_r"])
    assert subgroup_order == 680564733841876926932320129493409985129
    four_sign_mul = 10 * b
    four_sign_sqr = 4 * b
    pair_sum_cardinality_ceiling = b * (b + 1) // 2
    # The target is uniform over r-1 nonidentity points.  A fixed first pair
    # and its four signs expose at most 4*C(B+1,2) distinct second-pair sums.
    success_numerator = 4 * pair_sum_cardinality_ceiling
    success_denominator = subgroup_order - 1
    expected_k_hits_mul_numerator = k * success_denominator * four_sign_mul
    expected_k_hits_mul_denominator = success_numerator
    q1414_queries = {
        "50pct_rank_success": 110435936,
        "95pct_rank_success": 209828278,
        "expected_rank_at_least_K": 220871871,
    }
    output = {
        "proposal_id": "Q1505", "candidate_id": None, "run_id": None,
        "curve_id_n83": protocol["curve_id"],
        "curve_id_n131": q1504["curve_id"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "result_sha256": sha(HERE / "result.json"),
        "q1504_analysis_sha256": sha(PARENT / "q20261012_n131_w6_direct_scan_budget/analysis.json"),
        "q1447_measurement_sha256": sha(q1447_path),
        "n83_full_scan_rows": len(result["rows"]),
        "n83_primary_batch_full_scans": sum(r["batch_pairs"] == 512 for r in result["rows"]),
        "n83_all_checksum_and_hit_matches": True,
        "n83_batch_screen_exploratory_seconds_median": {
            str(batch): statistics.median(r["result"]["scan_seconds"] for r in result["rows"]
                                          if r["batch_pairs"] == batch)
            for batch in protocol["batch_pairs_screen"]},
        "n83_four_sign_full_scan_mul_calls_before": 14 * b83,
        "n83_four_sign_full_scan_mul_calls_after_zero_hits": 10 * b83,
        "n131_exact_weight6_B": b, "n131_exact_weight6_K": k,
        "n131_four_sign_scan_batch_mul_calls_zero_hits": four_sign_mul,
        "n131_four_sign_scan_batch_sqr_calls_zero_hits": four_sign_sqr,
        "n131_four_sign_scan_batch_inversions_at_512_pairs": 4 * math.ceil((b // 2) / 512),
        "n131_four_sign_scan_mul_log2": math.log2(four_sign_mul),
        "n131_q1414_one_full_scan_per_query_scenario": {
            label: {"queries": n, "batch_mul_calls": n * four_sign_mul,
                    "batch_mul_log2": math.log2(n * four_sign_mul),
                    "gap_above_2pow61_bits": math.log2(n * four_sign_mul) - 61}
            for label, n in q1414_queries.items()},
        "independent_uniform_first_pair_model": {
            "scope": "For each uniform nonidentity target and fixed first x-pair chosen independently of the target, four signed complements are fully scanned. At most four unordered signed-base pair-sum sets can hit. This model omits first-pair search, rank novelty, setup, LA and descent. It is not a bound on target-guided first-pair selection or a complete solve.",
            "subgroup_order": str(subgroup_order),
            "unordered_second_pairs_ceiling": pair_sum_cardinality_ceiling,
            "four_sign_hit_probability_upper_numerator": success_numerator,
            "four_sign_hit_probability_upper_denominator": str(success_denominator),
            "four_sign_hit_probability_upper_log2": math.log2(success_numerator) - math.log2(success_denominator),
            "expected_full_scans_for_K_hits_lower_log2":
                math.log2(k) + math.log2(success_denominator) - math.log2(success_numerator),
            "expected_batch_mul_calls_for_K_hits_lower_log2":
                math.log2(expected_k_hits_mul_numerator) - math.log2(expected_k_hits_mul_denominator),
            "gap_above_2pow61_bits":
                math.log2(expected_k_hits_mul_numerator) - math.log2(expected_k_hits_mul_denominator) - 61,
            "rank_novelty_charged": False,
        },
        "complete_n131_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
    }
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
