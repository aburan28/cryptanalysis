#!/usr/bin/env python3
"""Compare Q1469 prefixes on frozen ordinary N53/N83 queries."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from priorities import MODES

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1467 = PARENT / "q20261011_wdsat_order"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification_path = HERE / "verification.json"
    verification = json.loads(verification_path.read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 12
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert tuple(protocol["modes"]) == MODES
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap == 1 << 20
    rows = []
    winners = []
    for degree in (53, 83):
        name = f"n{degree}"
        baseline_path = Q1467 / "runs" / f"{name}_ordinary" / "selector_first" / "receipt.json"
        baseline = json.loads(baseline_path.read_text())
        assert baseline["status"] == "BRANCH_CAP_REACHED"
        degree_rows = []
        for mode in MODES:
            control_path = HERE / "runs" / f"{name}_full_lock" / mode / "receipt.json"
            control = json.loads(control_path.read_text())
            assert control["status"] == "SAT_REPLAYED_XCNF"
            path = HERE / "runs" / f"{name}_ordinary" / mode / "receipt.json"
            result = json.loads(path.read_text())
            assert result["status"] == "BRANCH_CAP_REACHED"
            assert result["branch_exact_at_cap"] == cap
            for key in ("curve_id", "workload_id", "public_target", "factor_base_actual_B",
                        "factor_base_folded_columns_K", "factor_base_enumerated_set_sha256",
                        "archive_sha256", "source_archive_sha256"):
                assert result[key] == baseline[key]
            assert result["left_branch_attempt_limit"] == baseline["left_branch_attempt_limit"] == cap
            assert result["cpu_soft_limit_seconds"] == baseline["cpu_soft_limit_seconds"]
            assert result["wall_limit_seconds"] == baseline["wall_limit_seconds"]
            ratio = baseline["user_cpu_seconds"] / result["user_cpu_seconds"]
            row = {"degree": degree, "mode": mode, "curve_id": result["curve_id"],
                   "workload_id": result["workload_id"],
                   "factor_base_actual_B": result["factor_base_actual_B"],
                   "factor_base_folded_columns_K": result["factor_base_folded_columns_K"],
                   "status": result["status"], "left_branches": cap,
                   "user_cpu_seconds_exploratory": result["user_cpu_seconds"],
                   "baseline_user_cpu_seconds_exploratory": baseline["user_cpu_seconds"],
                   "baseline_over_variant_user_cpu_ratio_at_same_cap": ratio,
                   "baseline_over_variant_user_cpu_log2_at_same_cap": math.log2(ratio),
                   "wall_seconds_exploratory": result["wall_seconds_exploratory"],
                   "natural_relation_yield_estimate": result["natural_relation_yield_estimate"],
                   "complete_decomposition_work_log2": result["complete_solve_work_log2"],
                   "receipt_sha256": sha(path), "control_receipt_sha256": sha(control_path),
                   "baseline_receipt_sha256": sha(baseline_path)}
            degree_rows.append(row)
            rows.append(row)
        winner = min(degree_rows, key=lambda row: row["user_cpu_seconds_exploratory"])
        winners.append({"degree": degree, "mode": winner["mode"],
                        "user_cpu_seconds_exploratory": winner["user_cpu_seconds_exploratory"],
                        "baseline_over_variant_user_cpu_ratio_at_same_cap": winner[
                            "baseline_over_variant_user_cpu_ratio_at_same_cap"]})
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    output = {"proposal_id": "Q1469", "candidate_id": None,
              "status": "COMPLETE_PREFIX_SCREEN", "left_branch_cap": cap,
              "hypotheses_per_degree": len(MODES), "rows": rows,
              "single_query_exploratory_winners": winners,
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
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1469", output["status"], len(rows), "ordinary rows")


if __name__ == "__main__":
    main()
