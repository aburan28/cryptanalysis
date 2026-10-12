#!/usr/bin/env python3
"""Check exact replay and account paired-sign native field calls."""
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1501 = PARENT / "q20261012_n83_complement_pair_probe"
Q1462 = PARENT / "q20261011_n131_pair_budget/analysis.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol = read(HERE / "protocol.json")
    result = read(HERE / "result.json")
    baseline = read(Q1501 / "full_result.json")
    control = read(HERE / "control_result.json")
    model = read(Q1462)
    b, k = protocol["factor_base_actual_B"], protocol["factor_base_folded_columns_K"]
    assert b == 2 * protocol["scan_pairs_per_complement"]
    assert len(result["rows"]) == len(baseline["rows"]) == 8
    assert control["native_result"]["hits"] >= 1
    for new, old in zip(result["rows"], baseline["rows"]):
        assert new["input"] == old["input"] and new["complement_index"] == old["complement_index"]
        assert new["status"] == old["status"] == "COMPLETE"
        assert new["result"]["scanned"] == old["result"]["scanned"] == b
        assert new["result"]["checksum_hex"] == old["result"]["checksum_hex"]
        assert new["result"]["hits"] == old["result"]["hits"] == 0
        assert new["result"]["exceptional_pairs"] == old["result"]["exceptional"] == 0
    old_mul = 20 * b
    new_mul = 14 * b
    old_inv = 4 * math.ceil(b / 512)
    new_inv = 4 * math.ceil((b // 2) / protocol["batch_pairs"])
    n131_b, n131_k = model["conditional_B"], model["conditional_K"]
    output = {
        "proposal_id": "Q1502", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "result_sha256": sha(HERE / "result.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "q1501_full_result_sha256": sha(Q1501 / "full_result.json"),
        "q1462_conditional_model_sha256": sha(Q1462),
        "complete_complements": len(result["rows"]),
        "matching_full_xor_checksums": len(result["rows"]),
        "n83_group_additions_per_fixed_first_pair": 4 * b,
        "n83_baseline_mul_calls_excluding_inversion_internals": old_mul,
        "n83_signed_pair_mul_calls_excluding_inversion_internals": new_mul,
        "n83_field_mul_call_reduction_fraction": (old_mul - new_mul) / old_mul,
        "n83_field_mul_call_reduction_log2_bits": math.log2(old_mul / new_mul),
        "n83_squaring_calls_both": 4 * b,
        "n83_baseline_batch_inversions_per_fixed_first_pair": old_inv,
        "n83_signed_pair_batch_inversions_per_fixed_first_pair": new_inv,
        "n83_old_scan_seconds_median_exploratory": statistics.median(
            r["result"]["scan_seconds"] for r in baseline["rows"]),
        "n83_new_scan_seconds_median_exploratory": statistics.median(
            r["result"]["scan_seconds"] for r in result["rows"]),
        "n83_paired_wall_ratios_exploratory": [
            old["result"]["scan_seconds"] / new["result"]["scan_seconds"]
            for new, old in zip(result["rows"], baseline["rows"])],
        "n131_base_status": "Q1462 sampled conditional weight-seven base",
        "n131_conditional_B": n131_b, "n131_conditional_K": n131_k,
        "n131_signed_pair_mul_calls_per_fixed_first_pair_excluding_inversion_internals": 14 * n131_b,
        "n131_signed_pair_mul_calls_per_fixed_first_pair_log2": math.log2(14 * n131_b),
        "n131_optimistic_one_scan_per_novel_row_mul_calls_log2": math.log2(14 * n131_b * n131_k),
        "n131_optimistic_gap_above_2pow61_field_mul_call_bits": math.log2(14 * n131_b * n131_k) - 61,
        "n131_model_assumptions": "Every fixed first pair yields a novel rank row after one complete four-sign scan, with K rows required. Counts exclude inversion internals, failed first pairs, setup, matrix, target handling, and verification; this is a conditional stage model.",
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("PASS Q1502", output["n83_field_mul_call_reduction_log2_bits"],
          output["n131_optimistic_one_scan_per_novel_row_mul_calls_log2"])


if __name__ == "__main__":
    main()
