#!/usr/bin/env python3
"""Report Q1468's deeper selector-first search and challenge accounting."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1467 = PARENT / "q20261011_wdsat_order"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification_path = HERE / "verification.json"
    verification = json.loads(verification_path.read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    protocol = json.loads((HERE / "protocol.json").read_text())
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap == 1 << 23
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        control_path = HERE / "runs" / f"{name}_full_lock" / "selector_first" / "receipt.json"
        control = json.loads(control_path.read_text())
        assert control["status"] == "SAT_REPLAYED_XCNF"
        path = HERE / "runs" / f"{name}_ordinary" / "selector_first" / "receipt.json"
        run = json.loads(path.read_text())
        parent_path = Q1467 / "runs" / f"{name}_ordinary" / "selector_first" / "receipt.json"
        parent = json.loads(parent_path.read_text())
        for key in ("curve_id", "workload_id", "public_target", "factor_base_actual_B",
                    "factor_base_folded_columns_K", "factor_base_enumerated_set_sha256",
                    "archive_sha256", "source_archive_sha256"):
            assert run[key] == parent[key]
        assert parent["status"] == "BRANCH_CAP_REACHED"
        rows.append({"degree": degree, "curve_id": run["curve_id"],
                     "workload_id": run["workload_id"],
                     "factor_base_actual_B": run["factor_base_actual_B"],
                     "factor_base_folded_columns_K": run["factor_base_folded_columns_K"],
                     "status": run["status"],
                     "branch_lower_bound": run["branch_lower_bound"],
                     "branch_lower_bound_log2": (math.log2(run["branch_lower_bound"])
                                                  if run["branch_lower_bound"] else None),
                     "branch_exact_at_cap": run["branch_exact_at_cap"],
                     "previous_branch_cap": parent["left_branch_attempt_limit"],
                     "user_cpu_seconds_exploratory": run["user_cpu_seconds"],
                     "wall_seconds_exploratory": run["wall_seconds_exploratory"],
                     "maxrss_child_bytes_darwin": run["maxrss_child_bytes_darwin"],
                     "natural_relation_yield_estimate": run["natural_relation_yield_estimate"],
                     "complete_decomposition_work_log2": run["complete_solve_work_log2"],
                     "receipt_sha256": sha(path), "control_receipt_sha256": sha(control_path),
                     "parent_receipt_sha256": sha(parent_path)})
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    output = {"proposal_id": "Q1468", "candidate_id": None,
              "status": "COMPLETE_DEEP_SELECTOR_SCREEN", "left_branch_cap": cap,
              "rows": rows, "verification_sha256": sha(verification_path),
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
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1468", output["status"], len(rows), "ordinary rows")


if __name__ == "__main__":
    main()
