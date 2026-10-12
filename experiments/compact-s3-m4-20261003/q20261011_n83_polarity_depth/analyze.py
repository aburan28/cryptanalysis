#!/usr/bin/env python3
"""Compare the two deep N83 propagation prefixes and update attempt totals."""
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
    earlier_path = PARENT / "q20261011_n83_propagation_probe/analysis.json"
    earlier = json.loads(earlier_path.read_text())
    assert earlier["proposal_id"] == "Q1474"
    assert earlier["workload_id"] == protocol["workload_id"]
    rows = []
    for phase in protocol["phase_order"]:
        path = HERE / "runs" / f"phase{phase}" / "receipt.json"
        if not path.exists():
            break
        row = json.loads(path.read_text())
        assert row["proposal_id"] == "Q1475" and row["phase"] == phase
        rows.append({"phase": phase, "flip_ids": row["flip_ids"],
                     "status": row["status"], "branch_lower_bound": row[
                         "branch_lower_bound"],
                     "cnf_set_true_calls_at_checkpoint": row[
                         "cnf_set_true_calls_at_checkpoint"],
                     "xor_set_true_calls_at_checkpoint": row[
                         "xor_set_true_calls_at_checkpoint"],
                     "solver_wall_seconds_exploratory": row[
                         "solver_wall_seconds_exploratory"],
                     "user_cpu_seconds_exploratory": row["user_cpu_seconds"],
                     "receipt_sha256": sha(path)})
    assert len(rows) == drive["new_ordinary_attempts"] == 2
    assert all(row["status"] == "CHECKPOINT_TERMINATED" and row[
        "branch_lower_bound"] == protocol["checkpoint_left_branches"] for row in rows)
    plain, flipped = rows
    for kind in ("cnf", "xor"):
        key = f"{kind}_set_true_calls_at_checkpoint"
        flipped[f"{kind}_calls_over_plain"] = flipped[key] / plain[key]
        flipped[f"{kind}_reduction_fraction"] = 1 - flipped[f"{kind}_calls_over_plain"]
    result = {
        "proposal_id": "Q1475", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "isogeny": "none", "stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "checkpoint_left_branches": protocol["checkpoint_left_branches"],
        "rows": rows,
        "plain_vs_selector2140_cnf_reduction_fraction": flipped[
            "cnf_reduction_fraction"],
        "plain_vs_selector2140_xor_reduction_fraction": flipped[
            "xor_reduction_fraction"],
        "q1474_checkpoint_left_branches": earlier["checkpoint_left_branches"],
        "q1474_selector2140_cnf_calls_over_plain": earlier["rows"][1][
            "cnf_calls_over_plain"],
        "q1474_selector2140_xor_calls_over_plain": earlier["rows"][1][
            "xor_calls_over_plain"],
        "ordinary_attempts_same_target_q1472_q1474_q1475": earlier[
            "ordinary_attempts_same_target_q1472_plus_q1474"] + len(rows),
        "charged_target_dependent_wall_seconds_exploratory_all_attempts": earlier[
            "charged_target_dependent_wall_seconds_exploratory_q1472_plus_q1474"] +
            drive["new_ordinary_wall_seconds_exploratory"],
        "solver_child_user_cpu_seconds_exploratory_all_attempts": earlier[
            "solver_child_user_cpu_seconds_exploratory_q1472_plus_q1474"] +
            drive["new_ordinary_user_cpu_seconds"],
        "new_verified_relations": drive["new_verified_relations"],
        "natural_relation_yield_estimate": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
        "separate_conditional_n131_pair_index_counted_pair_additions_log2": earlier[
            "separate_conditional_n131_pair_index_counted_pair_additions_log2"],
        "separate_conditional_n131_pair_index_gap_pair_add_bits": earlier[
            "separate_conditional_n131_pair_index_gap_pair_add_bits"],
        "unit_boundary": "matched-prefix CNF and XOR set_true calls, kept separate from pair additions; no complete ordinary relation",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "q1474_analysis_sha256": sha(earlier_path),
        "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1475", len(rows), "matched phases; reductions", round(
        100 * result["plain_vs_selector2140_cnf_reduction_fraction"], 2),
        round(100 * result["plain_vs_selector2140_xor_reduction_fraction"], 2))


if __name__ == "__main__":
    main()
