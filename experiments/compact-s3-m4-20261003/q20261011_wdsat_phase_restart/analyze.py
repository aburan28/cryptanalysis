#!/usr/bin/env python3
"""Summarize all charged Q1472 attempts without promoting censored searches."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    validation = json.loads((HERE / "validation.json").read_text())
    assert validation["status"] == "PASS"
    pair_path = HERE.parent / "q20261011_n131_pair_budget/analysis.json"
    pair = json.loads(pair_path.read_text())
    assert pair["proposal_id"] == "Q1462" and pair["complete_solve_work_log2"] is None
    attempts = drive["attempts"]
    branch_lower_bound = sum(row["branch_lower_bound"] for row in attempts)
    exact_branches = (branch_lower_bound if all(
        row["status"] == "BRANCH_CAP_REACHED" for row in attempts) else None)
    statuses = {name: sum(row["status"] == name for row in attempts)
                for name in sorted({row["status"] for row in attempts})}
    verified_relations = statuses.get("VERIFIED_RELATION", 0)
    assert verified_relations <= 1
    phase_zero_cpu = attempts[0]["user_cpu_seconds"]
    phase_rows = [{
        "phase": row["phase"], "status": row["status"],
        "branch_lower_bound": row["branch_lower_bound"],
        "user_cpu_seconds_exploratory": row["user_cpu_seconds"],
        "target_dependent_run_wall_seconds_exploratory": row[
            "run_wall_seconds_exploratory"],
        "phase_zero_over_phase_user_cpu_ratio_at_same_cap": (
            phase_zero_cpu / row["user_cpu_seconds"]
            if row["status"] == attempts[0]["status"] == "BRANCH_CAP_REACHED"
            else None),
    } for row in attempts]
    output = {
        "proposal_id": "Q1472", "candidate_id": None,
        "curve_id": target["curve_id"], "workload_id": target["workload_id"],
        "target_count": 1, "isogeny": "none",
        "factor_base_actual_B": target["factor_base_actual_B"],
        "factor_base_folded_columns_K": target["factor_base_folded_columns_K"],
        "attempt_count": len(attempts), "ordinary_status_mix": statuses,
        "stop_status": drive["stop_status"],
        "planned_phase_indices": drive["planned_phase_indices"],
        "unattempted_ordinary_phase_indices": drive[
            "unattempted_ordinary_phase_indices"],
        "phase_rows": phase_rows,
        "verified_natural_relations": verified_relations,
        "total_left_branch_attempts_lower_bound": branch_lower_bound,
        "total_left_branch_attempts_exact_if_all_at_cap": exact_branches,
        "log2_branch_attempts_lower_bound": (
            math.log2(branch_lower_bound) if branch_lower_bound else None),
        "total_solver_child_user_cpu_seconds_exploratory": drive[
            "total_user_cpu_seconds_exploratory"],
        "total_target_dependent_wall_seconds_exploratory": drive[
            "total_target_dependent_wall_seconds_exploratory"],
        "host_isolation": protocol["limits"]["host_isolation"],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_decomposition_work_log2": None,
        "complete_n131_one_target_work_log2": None,
        "challenge_threshold_log2": 61,
        "challenge_gap_bits_on_comparable_full_work": None,
        "conditional_pair_index_n131_counted_pair_add_log2": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"],
        "conditional_pair_index_gap_above_2pow61_pair_add_bits": pair[
            "conditional_gap_above_2pow61_pair_add_bits"],
        "conditional_pair_index_policy": "Q1462 sampled N131 W<=7 base, full quotient pair index, optimistic rank novelty",
        "conditional_pair_index_unit": "counted pair additions; separate from SAT branches and the N83 W<=5 base",
        "conditional_pair_index_analysis_sha256": sha(pair_path),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "validation_sha256": sha(HERE / "validation.json"),
        "source_sha256": sha(Path(__file__)),
    }
    path = HERE / "analysis.json"
    assert not path.exists()
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
