#!/usr/bin/env python3
"""Summarize the deeper exact ordinary branch measurements and N131 ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification_path = HERE / "verification.json"
    verification = json.loads(verification_path.read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    protocol = json.loads((HERE / "protocol.json").read_text())
    budget = protocol["limits"]["left_branch_attempts_per_run"]
    assert budget == 1 << 20
    rows = []
    for degree in (53, 83):
        control_path = HERE / "runs" / f"n{degree}_full_lock/receipt.json"
        control = json.loads(control_path.read_text())
        assert control["status"] == "SAT_REPLAYED_XCNF"
        path = HERE / "runs" / f"n{degree}_ordinary/receipt.json"
        receipt = json.loads(path.read_text())
        assert receipt["status"] == "BRANCH_CAP_REACHED"
        assert receipt["branch_exact_at_cap"] == budget
        assert receipt["complete_solve_work_log2"] is None
        rows.append({"degree": degree, "curve_id": receipt["curve_id"],
                     "workload_id": receipt["workload_id"],
                     "factor_base_actual_B": receipt["factor_base_actual_B"],
                     "factor_base_folded_columns_K": receipt["factor_base_folded_columns_K"],
                     "factor_base_enumerated_set_sha256": receipt["factor_base_enumerated_set_sha256"],
                     "status": receipt["status"],
                     "left_branch_attempts": budget,
                     "user_cpu_seconds_exploratory": receipt["user_cpu_seconds"],
                     "system_cpu_seconds_exploratory": receipt["system_cpu_seconds"],
                     "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                     "maxrss_child_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                     "natural_relation_yield_estimate": None,
                     "complete_decomposition_work_log2": None,
                     "receipt_sha256": sha(path),
                     "control_receipt_sha256": sha(control_path)})
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    output = {"proposal_id": "Q1466", "candidate_id": None,
              "status": "COMPLETE_DEEP_BRANCH_SCREEN",
              "branch_count_definition": protocol["solver"]["branch_metric"],
              "left_branch_cap": budget, "rows": rows,
              "n83_over_n53_total_user_cpu_ratio_at_same_branch_cap": (
                  rows[1]["user_cpu_seconds_exploratory"] /
                  rows[0]["user_cpu_seconds_exploratory"]),
              "verification_sha256": sha(verification_path),
              "freeze_sha256": sha(HERE / "freeze.json"),
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
    print("Q1466", output["status"], len(rows), "ordinary rows")


if __name__ == "__main__":
    main()
