#!/usr/bin/env python3
"""Compare frozen XOR-Gauss statuses with the plain WDSat baseline."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1469 = PARENT / "q20261011_wdsat_prefix_search"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification_path = HERE / "verification.json"
    verification = json.loads(verification_path.read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    protocol = json.loads((HERE / "protocol.json").read_text())
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap == 1 << 20
    rows = []
    for degree in (53, 83):
        name = f"n{degree}"
        mode = protocol["selected_mode_by_degree"][str(degree)]
        control_path = HERE / "runs" / f"{name}_full_lock" / mode / "receipt.json"
        control = json.loads(control_path.read_text())
        path = HERE / "runs" / f"{name}_ordinary" / mode / "receipt.json"
        run = json.loads(path.read_text())
        baseline_path = Q1469 / "runs" / f"{name}_ordinary" / mode / "receipt.json"
        baseline = json.loads(baseline_path.read_text())
        assert baseline["status"] == "BRANCH_CAP_REACHED"
        for key in ("curve_id", "workload_id", "public_target", "factor_base_actual_B",
                    "factor_base_folded_columns_K", "factor_base_enumerated_set_sha256",
                    "archive_sha256", "source_archive_sha256", "binary_sha256"):
            assert run[key] == baseline[key]
        assert run["left_branch_attempt_limit"] == baseline["left_branch_attempt_limit"] == cap
        assert run["cpu_soft_limit_seconds"] == baseline["cpu_soft_limit_seconds"]
        assert run["wall_limit_seconds"] == baseline["wall_limit_seconds"]
        same_count = (run["status"] == "BRANCH_CAP_REACHED" and
                      run["branch_exact_at_cap"] == cap)
        ratio = (baseline["user_cpu_seconds"] / run["user_cpu_seconds"]
                 if same_count and run["user_cpu_seconds"] > 0 else None)
        upper_exclusive = (2 * run["branch_lower_bound"]
                           if run["status"] == "CPU_CAP_SEARCH_STARTED" and
                           run["branch_lower_bound"] else None)
        min_xg_cpu_per_branch = (run["user_cpu_seconds"] / upper_exclusive
                                 if upper_exclusive else None)
        plain_cpu_per_branch = baseline["user_cpu_seconds"] / cap
        rows.append({"degree": degree, "mode": mode,
                     "curve_id": run["curve_id"], "workload_id": run["workload_id"],
                     "factor_base_actual_B": run["factor_base_actual_B"],
                     "factor_base_folded_columns_K": run["factor_base_folded_columns_K"],
                     "control_status": control["status"],
                     "ordinary_status": run["status"],
                     "search_started": run["search_started"],
                     "after_xor_init": run["after_xor_init"],
                     "branch_lower_bound": run["branch_lower_bound"],
                     "branch_upper_bound_exclusive_from_checkpoints": upper_exclusive,
                     "branch_exact_at_cap": run["branch_exact_at_cap"],
                     "user_cpu_seconds_exploratory": run["user_cpu_seconds"],
                     "baseline_user_cpu_seconds_exploratory": baseline["user_cpu_seconds"],
                     "xg_user_cpu_per_branch_lower_bound_seconds": min_xg_cpu_per_branch,
                     "plain_user_cpu_per_branch_seconds": plain_cpu_per_branch,
                     "xg_over_plain_user_cpu_per_branch_lower_bound": (
                         min_xg_cpu_per_branch / plain_cpu_per_branch
                         if min_xg_cpu_per_branch else None),
                     "baseline_over_xg_user_cpu_ratio_at_same_cap": ratio,
                     "baseline_over_xg_user_cpu_log2_at_same_cap": math.log2(ratio) if ratio else None,
                     "wall_seconds_exploratory": run["wall_seconds_exploratory"],
                     "maxrss_child_bytes_darwin": run["maxrss_child_bytes_darwin"],
                     "natural_relation_group_replay_status": None,
                     "natural_relation_yield_estimate": None,
                     "complete_decomposition_work_log2": None,
                     "receipt_sha256": sha(path), "control_receipt_sha256": sha(control_path),
                     "baseline_receipt_sha256": sha(baseline_path)})
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    output = {"proposal_id": "Q1471", "candidate_id": None,
              "status": "COMPLETE_XG_SCREEN", "left_branch_cap": cap,
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
    print("Q1471", output["status"], len(rows), "ordinary rows")


if __name__ == "__main__":
    main()
