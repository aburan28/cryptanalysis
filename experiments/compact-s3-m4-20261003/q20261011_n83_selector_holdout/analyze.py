#!/usr/bin/env python3
"""Price Q1476's fresh-target polarity reversal without mixing work units."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1475 = PARENT / "q20261011_n83_polarity_depth"
Q1462 = PARENT / "q20261011_n131_pair_budget"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    selected_path = Q1475 / "analysis.json"
    selected = json.loads(selected_path.read_text())
    pair_path = Q1462 / "analysis.json"
    pair = json.loads(pair_path.read_text())
    assert selected["proposal_id"] == "Q1475" and pair["proposal_id"] == "Q1462"
    assert target["workload_id"] != selected["workload_id"]
    assert protocol["phase_order"] == [0, 1]
    rows = []
    for phase in protocol["phase_order"]:
        path = HERE / "runs" / f"phase{phase}" / "receipt.json"
        if not path.exists():
            break
        row = json.loads(path.read_text())
        assert row["proposal_id"] == "Q1476" and row["phase"] == phase
        rows.append({"phase": phase, "flip_ids": row["flip_ids"],
                     "status": row["status"],
                     "branch_lower_bound": row["branch_lower_bound"],
                     "cnf_set_true_calls_at_checkpoint": row[
                         "cnf_set_true_calls_at_checkpoint"],
                     "xor_set_true_calls_at_checkpoint": row[
                         "xor_set_true_calls_at_checkpoint"],
                     "solver_wall_seconds_exploratory": row[
                         "solver_wall_seconds_exploratory"],
                     "user_cpu_seconds_exploratory": row["user_cpu_seconds"],
                     "receipt_sha256": sha(path)})
    assert len(rows) == drive["new_ordinary_attempts"] == 2
    plain, flipped = rows
    assert all(row["status"] == "CHECKPOINT_TERMINATED" and row[
        "branch_lower_bound"] == protocol["checkpoint_left_branches"] for row in rows)
    for kind in ("cnf", "xor"):
        key = f"{kind}_set_true_calls_at_checkpoint"
        flipped[f"{kind}_calls_over_plain"] = flipped[key] / plain[key]
        flipped[f"{kind}_increase_fraction"] = flipped[f"{kind}_calls_over_plain"] - 1
    result = {
        "proposal_id": "Q1476", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": target["workload_id"],
        "isogeny": "none", "stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": target[
            "factor_base_enumerated_set_sha256"],
        "checkpoint_left_branches": protocol["checkpoint_left_branches"],
        "holdout_count": 1,
        "rows": rows,
        "holdout_flip2140_cnf_calls_over_plain": flipped["cnf_calls_over_plain"],
        "holdout_flip2140_xor_calls_over_plain": flipped["xor_calls_over_plain"],
        "selected_target_flip2140_cnf_calls_over_plain": selected["rows"][1][
            "cnf_calls_over_plain"],
        "selected_target_flip2140_xor_calls_over_plain": selected["rows"][1][
            "xor_calls_over_plain"],
        "universal_prefix_dominance_refuted_on_holdout": (
            flipped["cnf_calls_over_plain"] > 1 and
            flipped["xor_calls_over_plain"] > 1),
        "target_preimage_seconds_exploratory": drive[
            "target_preimage_seconds_exploratory"],
        "formula_build_seconds_exploratory": drive[
            "formula_build_seconds_exploratory"],
        "solver_attempt_wall_seconds_exploratory": drive[
            "solver_attempt_wall_seconds_exploratory"],
        "target_dependent_wall_phase_sum_seconds_exploratory": drive[
            "target_dependent_wall_phase_sum_seconds_exploratory"],
        "solver_child_user_cpu_seconds_exploratory": drive[
            "solver_child_user_cpu_seconds_exploratory"],
        "verified_natural_relations": drive["new_verified_relations"],
        "natural_relation_yield_estimate": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
        "separate_conditional_n131_pair_index_counted_pair_additions_log2": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"],
        "separate_conditional_n131_pair_index_gap_pair_add_bits": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"] - 61,
        "unit_boundary": "CNF and XOR set_true calls are separate prefix counters; pair additions are a distinct unit; no completed ordinary relation",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "input_freeze_sha256": sha(HERE / "input_freeze.json"),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "target_sha256": sha(HERE / "target.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "selected_analysis_sha256": sha(selected_path),
        "pair_analysis_sha256": sha(pair_path),
        "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1476 holdout", target["workload_id"],
          round(100 * flipped["cnf_increase_fraction"], 2),
          round(100 * flipped["xor_increase_fraction"], 2))


if __name__ == "__main__":
    main()
