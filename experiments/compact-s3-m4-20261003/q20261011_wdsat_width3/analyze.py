#!/usr/bin/env python3
"""Compare frozen width-three and width-four WDSat cells at equal branches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification = json.loads((HERE / "verification.json").read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 8
    protocol = json.loads((HERE / "protocol.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    budget = protocol["limits"]["left_branch_attempts_per_run"]
    rows = []
    for degree in (53, 83):
        cell = f"n{degree}_ordinary"
        for variant in ("plain", "xor_gauss"):
            width3_path = HERE / "runs" / cell / variant / "receipt.json"
            width4_path = Q1464 / "runs" / cell / variant / "receipt.json"
            width3 = json.loads(width3_path.read_text())
            width4 = json.loads(width4_path.read_text())
            assert width3["status"] == width4["status"] == "BRANCH_CAP_REACHED"
            assert width3["branch_exact_at_cap"] == width4["branch_exact_at_cap"] == budget
            assert width3["curve_id"] == width4["curve_id"]
            assert width3["workload_id"] == width4["workload_id"]
            assert width3["public_target"] == width4["public_target"]
            assert width3["factor_base_enumerated_set_sha256"] == width4["factor_base_enumerated_set_sha256"]
            assert width3["source_archive_sha256"] == width4["source_archive_sha256"]
            stats = prepared["cells"][cell]["stats"]
            rows.append({"degree": degree, "variant": variant,
                         "curve_id": width3["curve_id"],
                         "workload_id": width3["workload_id"],
                         "factor_base_actual_B": width3["factor_base_actual_B"],
                         "factor_base_folded_columns_K": width3["factor_base_folded_columns_K"],
                         "max_cnf_width_new": 3, "width3_auxiliary_variables": stats["auxiliary_variables"],
                         "width3_rows": stats["derived_rows"],
                         "left_branch_attempts": budget,
                         "width3_user_cpu_seconds_exploratory": width3["user_cpu_seconds"],
                         "width4_user_cpu_seconds_exploratory": width4["user_cpu_seconds"],
                         "width3_over_width4_user_cpu_ratio_exploratory": (
                             width3["user_cpu_seconds"] / width4["user_cpu_seconds"]),
                         "width3_maxrss_child_bytes_darwin": width3["maxrss_child_bytes_darwin"],
                         "width4_maxrss_child_bytes_darwin": width4["maxrss_child_bytes_darwin"],
                         "width3_receipt_sha256": sha(width3_path),
                         "width4_receipt_sha256": sha(width4_path),
                         "complete_decomposition_work_log2": None})
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    output = {"proposal_id": "Q1465", "candidate_id": None,
              "status": "COMPLETE_FIXED_BRANCH_WIDTH_SCREEN",
              "controlled_variable": protocol["controlled_variable"],
              "left_branch_cap": budget, "rows": rows,
              "verification_sha256": sha(HERE / "verification.json"),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "q1464_analysis_sha256": sha(Q1464 / "analysis.json"),
              "conditional_n131_pair_reference": {
                  "analysis_sha256": sha(q1462_path),
                  "counted_pair_add_attempts_log2": q1462[
                      "conditional_full_table_counted_pair_add_attempts_log2"],
                  "gap_above_2pow61_pair_add_bits": q1462[
                      "conditional_gap_above_2pow61_pair_add_bits"]},
              "degree131_complete_solve_work_log2": None,
              "degree131_complete_solve_challenge_gap_bits": None,
              "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1465", output["status"], len(rows), "ordinary comparisons")


if __name__ == "__main__":
    main()
