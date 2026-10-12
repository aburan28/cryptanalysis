#!/usr/bin/env python3
"""Summarize selector work while preserving capped and censored statuses."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / "analysis.json"
    assert not path.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    validation = json.loads((HERE / "validation.json").read_text())
    assert validation["status"] == "PASS"
    pair_path = HERE.parent / "q20261011_n131_pair_budget/analysis.json"
    pair = json.loads(pair_path.read_text())
    assert pair["proposal_id"] == "Q1462"
    attempts = drive["ordinary_attempts"]
    branch_lower = sum(x["branch_lower_bound"] for x in attempts)
    cnf_lower = sum(x["cnf_set_true_calls_lower_bound"] for x in attempts)
    xor_lower = sum(x["xor_set_true_calls_lower_bound"] for x in attempts)
    phase0 = attempts[0] if attempts else None
    rows = []
    for attempt in attempts:
        receipt = json.loads((HERE / "runs/ordinary" /
                              f"phase{attempt['phase']}/receipt.json").read_text())
        assert receipt["status"] == attempt["status"]
        same_cap = (phase0 is not None and
                    phase0["status"] == attempt["status"] == "BRANCH_CAP_REACHED")
        base = (json.loads((HERE / "runs/ordinary/phase0/receipt.json").read_text())
                if same_cap else None)
        rows.append({
            "phase": attempt["phase"], "status": attempt["status"],
            "branch_lower_bound": attempt["branch_lower_bound"],
            "cnf_set_true_calls_lower_bound": attempt[
                "cnf_set_true_calls_lower_bound"],
            "xor_set_true_calls_lower_bound": attempt[
                "xor_set_true_calls_lower_bound"],
            "cnf_set_true_calls_exact_at_cap": (
                receipt["cnf_set_true_calls_final"] if
                receipt["status"] == "BRANCH_CAP_REACHED" else None),
            "xor_set_true_calls_exact_at_cap": (
                receipt["xor_set_true_calls_final"] if
                receipt["status"] == "BRANCH_CAP_REACHED" else None),
            "user_cpu_seconds_exploratory": attempt["user_cpu_seconds"],
            "wall_seconds_exploratory": attempt[
                "run_wall_seconds_exploratory"],
            "phase_over_plain_cnf_calls_at_same_cap": (
                receipt["cnf_set_true_calls_final"] /
                base["cnf_set_true_calls_final"] if same_cap and
                base["cnf_set_true_calls_final"] else None),
            "phase_over_plain_xor_calls_at_same_cap": (
                receipt["xor_set_true_calls_final"] /
                base["xor_set_true_calls_final"] if same_cap and
                base["xor_set_true_calls_final"] else None),
        })
    exact_all = bool(attempts) and all(
        x["status"] == "BRANCH_CAP_REACHED" for x in attempts)
    output = {
        "proposal_id": "Q1473", "candidate_id": None,
        "curve_id": target["curve_id"], "workload_id": target["workload_id"],
        "target_count": 1, "isogeny": "none",
        "factor_base_actual_B": target["factor_base_actual_B"],
        "factor_base_folded_columns_K": target["factor_base_folded_columns_K"],
        "stop_status": drive["stop_status"],
        "attempt_count": len(attempts), "phase_rows": rows,
        "verified_natural_relations": sum(
            x["status"] == "VERIFIED_RELATION" for x in attempts),
        "new_ordinary_branch_lower_bound": branch_lower,
        "new_ordinary_branch_log2_lower_bound": (
            math.log2(branch_lower) if branch_lower else None),
        "new_ordinary_cnf_set_true_calls_lower_bound": cnf_lower,
        "new_ordinary_xor_set_true_calls_lower_bound": xor_lower,
        "new_ordinary_branch_exact_if_all_at_cap": (
            branch_lower if exact_all else None),
        "new_ordinary_user_cpu_seconds_exploratory": drive[
            "new_ordinary_solver_child_user_cpu_seconds_exploratory"],
        "new_ordinary_wall_seconds_exploratory": drive[
            "new_ordinary_wall_seconds_exploratory"],
        "cumulative_same_target_wall_seconds_exploratory": drive[
            "cumulative_same_target_wall_seconds_exploratory"],
        "host_isolation": protocol["limits"]["host_isolation"],
        "complete_n83_one_target_work_log2": None,
        "complete_n131_one_target_work_log2": None,
        "challenge_threshold_log2": 61,
        "challenge_gap_bits_on_comparable_full_work": None,
        "conditional_pair_index_n131_counted_pair_add_log2": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"],
        "conditional_pair_index_gap_above_2pow61_pair_add_bits": pair[
            "conditional_gap_above_2pow61_pair_add_bits"],
        "conditional_pair_index_policy": "Q1462 sampled N131 W<=7 base, full quotient pair index, optimistic rank novelty",
        "conditional_pair_index_unit": "counted pair additions; distinct from CNF/XOR set_true calls",
        "conditional_pair_index_analysis_sha256": sha(pair_path),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "validation_sha256": sha(HERE / "validation.json"),
        "source_sha256": sha(Path(__file__)),
    }
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stop_status": output["stop_status"],
                      "attempt_count": output["attempt_count"],
                      "branch_lower_bound": branch_lower,
                      "cnf_calls_lower_bound": cnf_lower,
                      "xor_calls_lower_bound": xor_lower}, sort_keys=True))


if __name__ == "__main__":
    main()
