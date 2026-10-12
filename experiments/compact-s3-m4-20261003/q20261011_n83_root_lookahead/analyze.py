#!/usr/bin/env python3
"""Compare root-probe signals to observed N83 prefix-work rankings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1475 = PARENT / "q20261011_n83_polarity_depth"
Q1476 = PARENT / "q20261011_n83_selector_holdout"
Q1462 = PARENT / "q20261011_n131_pair_budget"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    selected_path, holdout_path = Q1475 / "analysis.json", Q1476 / "analysis.json"
    selected, holdout = (json.loads(path.read_text()) for path in
                         (selected_path, holdout_path))
    pair_path = Q1462 / "analysis.json"
    pair = json.loads(pair_path.read_text())
    assert [selected["workload_id"], holdout["workload_id"]] == protocol[
        "ordinary_workloads"]
    assert pair["proposal_id"] == "Q1462"
    records = []
    for label, previous in (("selected", selected), ("holdout", holdout)):
        path = HERE / "runs" / label / "receipt.json"
        receipt = json.loads(path.read_text())
        assert receipt["status"] == "ROOT_PROBES_RESTORED"
        assert receipt["workload_id"] == previous["workload_id"]
        minus, plus = receipt["root_rows"]
        assert [minus["literal"], plus["literal"]] == [-2140, 2140]
        calls_equal = all(minus[key] == plus[key] for key in
                          ("cnf_calls", "xor_calls"))
        assigned_equal = all(minus[key] == plus[key] for key in
                             ("cnf_new_assignments", "xor_new_assignments"))
        full = previous["rows"]
        assert len(full) == 2
        full_winner = 0 if all(full[0][f"{kind}_set_true_calls_at_checkpoint"] <
                               full[1][f"{kind}_set_true_calls_at_checkpoint"]
                               for kind in ("cnf", "xor")) else 1
        if full_winner == 1:
            assert all(full[1][f"{kind}_set_true_calls_at_checkpoint"] <
                       full[0][f"{kind}_set_true_calls_at_checkpoint"]
                       for kind in ("cnf", "xor"))
        records.append({"label": label, "workload_id": receipt["workload_id"],
                        "root_rows": receipt["root_rows"],
                        "root_calls_equal": calls_equal,
                        "root_assignments_equal": assigned_equal,
                        "root_call_preference": None if calls_equal else "mixed_or_nonzero",
                        "root_assignment_preference": None if assigned_equal else "mixed_or_nonzero",
                        "full_prefix_left_branches": 262144,
                        "full_prefix_cheaper_phase_both_units": full_winner,
                        "receipt_sha256": sha(path)})
    assert records[0]["full_prefix_cheaper_phase_both_units"] == 1
    assert records[1]["full_prefix_cheaper_phase_both_units"] == 0
    assert all(record["root_calls_equal"] and record["root_assignments_equal"]
               for record in records)
    result = {
        "proposal_id": "Q1477", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "records": records,
        "one_step_root_probe_discriminates_these_two_points": False,
        "root_probe_work_per_sign_per_point": {
            "cnf_set_true_calls": 2, "xor_set_true_calls": 2,
            "cnf_new_assignments": 1, "xor_new_assignments": 1},
        "separate_conditional_n131_pair_index_counted_pair_additions_log2": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"],
        "separate_conditional_n131_pair_index_gap_pair_add_bits": pair[
            "conditional_full_table_counted_pair_add_attempts_log2"] - 61,
        "natural_relation_yield_estimate": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "selected_analysis_sha256": sha(selected_path),
        "holdout_analysis_sha256": sha(holdout_path),
        "pair_analysis_sha256": sha(pair_path),
        "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1477 root probe equal on two ordinary points")


if __name__ == "__main__":
    main()
