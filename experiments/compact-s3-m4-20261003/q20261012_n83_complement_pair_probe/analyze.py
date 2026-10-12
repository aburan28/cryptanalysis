#!/usr/bin/env python3
"""Account exact fixed-first-pair work and a conditional N131 floor."""
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1462 = PARENT / "q20261011_n131_pair_budget/analysis.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    full = read(HERE / "full_result.json")
    control = read(HERE / "control_result.json")
    pilot = read(HERE / "result.json")
    model = read(Q1462)
    rows = full["rows"]
    b = full["factor_base_actual_B"]
    assert len(rows) == 8
    assert all(r["status"] == "COMPLETE" and
               r["result"]["scanned"] == b and
               r["result"]["exceptional"] == 0 and
               r["result"]["hits"] == 0 for r in rows)
    assert control["native_result"]["hits"] == 1
    for p in pilot["rows"]:
        full_row = next(r for r in rows if r["input"] == p["input"] and
                        r["complement_index"] == p["complement_index"])
        assert p["result"]["scanned"] == 1000000
        assert p["result"]["hits"] == 0
        assert p["result"]["exceptional"] == 0
        assert full_row["result"]["batch"] == 512
    n131_b, n131_k = model["conditional_B"], model["conditional_K"]
    n83_adds = 4 * b
    n131_adds = 4 * n131_b
    optimistic_rank_adds = n131_adds * n131_k
    out = {
        "proposal_id": "Q1501", "candidate_id": None, "run_id": None,
        "curve_id": full["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "full_result_sha256": sha(HERE / "full_result.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "pilot_result_sha256": sha(HERE / "result.json"),
        "q1462_conditional_model_sha256": sha(Q1462),
        "ordinary_targets": 2, "signed_complements_per_target": 4,
        "complete_fixed_first_pair_scans": len(rows),
        "n83_exact_base_size_B": b,
        "n83_scanned_group_additions_total": len(rows) * b,
        "n83_scanned_group_additions_per_fixed_first_pair": n83_adds,
        "n83_log2_group_additions_per_fixed_first_pair": math.log2(n83_adds),
        "n83_native_batch_mul_calls_per_first_pair_excluding_inversion_internals": 5 * n83_adds,
        "n83_native_batch_sqr_calls_per_first_pair_excluding_inversion_internals": n83_adds,
        "n83_native_batch_inversions_per_first_pair": 4 * math.ceil(b / 512),
        "n83_full_scan_hits": 0,
        "n83_full_scan_seconds_each_exploratory": [r["result"]["scan_seconds"] for r in rows],
        "n83_full_scan_seconds_median_exploratory": statistics.median(
            r["result"]["scan_seconds"] for r in rows),
        "n83_pilot_median_seconds_by_batch_exploratory": {
            str(size): statistics.median(r["result"]["scan_seconds"]
                                         for r in pilot["rows"] if r["batch"] == size)
            for size in (512, 2048)},
        "n131_base_status": "Q1462 sampled conditional weight-seven base",
        "n131_conditional_B": n131_b,
        "n131_conditional_K": n131_k,
        "n131_direct_scan_group_additions_per_fixed_first_pair": n131_adds,
        "n131_direct_scan_group_additions_per_fixed_first_pair_log2": math.log2(n131_adds),
        "n131_optimistic_one_scan_per_novel_row_group_additions": optimistic_rank_adds,
        "n131_optimistic_one_scan_per_novel_row_log2": math.log2(optimistic_rank_adds),
        "n131_optimistic_gap_above_2pow61_group_addition_bits":
            math.log2(optimistic_rank_adds) - 61,
        "n131_model_assumptions": "Every fixed first pair yields a novel rank row after one complete four-sign scan; K rows required; no setup, failed first pairs, matrix, descent, or verification charged. This is an optimistic direct-scan stage floor, not a predicted complete solve.",
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("PASS Q1501", out["n83_log2_group_additions_per_fixed_first_pair"],
          out["n131_optimistic_one_scan_per_novel_row_log2"])


if __name__ == "__main__":
    main()
