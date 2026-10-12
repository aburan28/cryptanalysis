#!/usr/bin/env python3
"""Report fixed-branch Q1464 stage costs and the separate N131 work model."""
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
    assert verification["status"] == "PASS" and len(verification["runs"]) == 8
    protocol = json.loads((HERE / "protocol.json").read_text())
    budget = protocol["limits"]["left_branch_attempts_per_run"]
    ordinary = {}
    for degree in (53, 83):
        per_variant = {}
        for variant in ("plain", "xor_gauss"):
            path = HERE / "runs" / f"n{degree}_ordinary" / variant / "receipt.json"
            receipt = json.loads(path.read_text())
            assert receipt["status"] == "BRANCH_CAP_REACHED"
            assert receipt["branch_exact_at_cap"] == budget
            assert receipt["complete_solve_work_log2"] is None
            per_variant[variant] = {
                "status": receipt["status"], "left_branch_attempts": budget,
                "user_cpu_seconds_exploratory": receipt["user_cpu_seconds"],
                "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                "maxrss_child_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                "receipt_sha256": sha(path)}
        ordinary[str(degree)] = {
            "variants": per_variant,
            "xor_gauss_over_plain_total_user_cpu_ratio_at_fixed_branch_cap": (
                per_variant["xor_gauss"]["user_cpu_seconds_exploratory"] /
                per_variant["plain"]["user_cpu_seconds_exploratory"]),
            "relation_yield_estimate": None,
            "complete_decomposition_work_log2": None}
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    assert q1462["proposal_id"] == "Q1462"
    output = {"proposal_id": "Q1464", "candidate_id": None,
              "status": "COMPLETE_CAPPED_STAGE_MEASUREMENT",
              "branch_count_definition": protocol["solver"]["branch_metric"],
              "left_branch_cap": budget, "ordinary": ordinary,
              "control_statuses": {f"n{row['degree']}_{row['variant']}": row["status"]
                                   for row in verification["runs"] if row["kind"] == "full_lock"},
              "verification_sha256": sha(verification_path),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "conditional_n131_pair_reference": {
                  "analysis_sha256": sha(q1462_path),
                  "curve_id": q1462["curve_id"],
                  "sampled_conditional_B": q1462["conditional_B"],
                  "sampled_conditional_K": q1462["conditional_K"],
                  "counted_pair_add_attempts_log2": q1462[
                      "conditional_full_table_counted_pair_add_attempts_log2"],
                  "gap_above_2pow61_pair_add_bits": q1462[
                      "conditional_gap_above_2pow61_pair_add_bits"]},
              "degree131_complete_solve_work_log2": None,
              "degree131_complete_solve_challenge_gap_bits": None,
              "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1464", output["status"], "N53/N83", budget, "branches")


if __name__ == "__main__":
    main()
