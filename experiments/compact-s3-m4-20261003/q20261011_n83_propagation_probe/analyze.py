#!/usr/bin/env python3
"""Summarize Q1474 matched-branch propagation counters and charged attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    prior_path = PARENT / "q20261011_wdsat_phase_restart/drive_receipt.json"
    prior = json.loads(prior_path.read_text())
    pair_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    pair = json.loads(pair_path.read_text())
    assert prior["proposal_id"] == "Q1472" and pair["proposal_id"] == "Q1462"
    assert prior["workload_id"] == protocol["workload_id"]
    rows = []
    for phase in protocol["phase_order"]:
        receipt_path = HERE / "runs" / f"phase{phase}" / "receipt.json"
        if not receipt_path.exists():
            break
        receipt = json.loads(receipt_path.read_text())
        rows.append({"phase": phase, "flip_ids": receipt["flip_ids"],
                     "status": receipt["status"],
                     "branch_lower_bound": receipt["branch_lower_bound"],
                     "cnf_set_true_calls_at_checkpoint": receipt[
                         "cnf_set_true_calls_at_checkpoint"],
                     "xor_set_true_calls_at_checkpoint": receipt[
                         "xor_set_true_calls_at_checkpoint"],
                     "user_cpu_seconds_exploratory": receipt["user_cpu_seconds"],
                     "wall_seconds_exploratory": receipt[
                         "solver_wall_seconds_exploratory"],
                     "receipt_sha256": sha(receipt_path)})
    assert len(rows) == drive["new_ordinary_attempts"]
    plain = rows[0]
    for row in rows:
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert row["branch_lower_bound"] == protocol["checkpoint_left_branches"]
            for kind in ("cnf", "xor"):
                key = f"{kind}_set_true_calls_at_checkpoint"
                row[f"{kind}_calls_over_plain"] = row[key] / plain[key]
        else:
            row["cnf_calls_over_plain"] = None
            row["xor_calls_over_plain"] = None
    comparable = [row for row in rows if row["status"] == "CHECKPOINT_TERMINATED"]
    dominated = [row for row in comparable if
                 all(row[f"{kind}_set_true_calls_at_checkpoint"] < plain[
                     f"{kind}_set_true_calls_at_checkpoint"] for kind in ("cnf", "xor"))]
    best = min(dominated, key=lambda row: (row["cnf_calls_over_plain"],
                                            row["xor_calls_over_plain"])) if dominated else None
    result = {
        "proposal_id": "Q1474", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "stage_code": "PDP4sat", "checkpoint_left_branches": protocol[
            "checkpoint_left_branches"],
        "rows": rows,
        "prefix_dominating_plain_best_phase": best["phase"] if best else None,
        "prefix_dominating_plain_best_flip_ids": best["flip_ids"] if best else None,
        "ordinary_attempts_same_target_q1472_plus_q1474": len(prior["attempts"]) + len(rows),
        "charged_target_dependent_wall_seconds_exploratory_q1472_plus_q1474":
            prior["total_target_dependent_wall_seconds_exploratory"] +
            drive["new_ordinary_wall_seconds_exploratory"],
        "solver_child_user_cpu_seconds_exploratory_q1472_plus_q1474":
            prior["total_user_cpu_seconds_exploratory"] +
            drive["new_ordinary_user_cpu_seconds"],
        "new_verified_relations": drive["new_verified_relations"],
        "natural_relation_yield_estimate": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
        "separate_conditional_n131_pair_index_counted_pair_additions_log2":
            pair["conditional_full_table_counted_pair_add_attempts_log2"],
        "separate_conditional_n131_pair_index_gap_pair_add_bits":
            pair["conditional_full_table_counted_pair_add_attempts_log2"] - 61,
        "unit_boundary": "CNF and XOR set_true calls are separate prefix counters; pair additions are a different unit; no completed ordinary solve cost",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "q1472_drive_sha256": sha(prior_path),
        "q1462_analysis_sha256": sha(pair_path),
        "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1474", len(rows), "phases; best prefix mask", result[
        "prefix_dominating_plain_best_flip_ids"])


if __name__ == "__main__":
    main()
