#!/usr/bin/env python3
"""Summarize exact Q1478 branch snapshots without extrapolating solve work."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    cells = {}
    for item in drive["rows"]:
        name, order = item["input"], item["order"]
        path = HERE / "runs" / f"{name}_{order}" / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = json.loads(path.read_text())
        if name == "control":
            continue
        assert row["status"] == "CHECKPOINT_TERMINATED"
        ready = row["ready_checkpoints"][-1]
        work = row["work_checkpoints"][-1]
        assert ready[0] == work[0] == protocol["branch_checkpoint"]
        first_ready = next((r[0] for r in row["ready_checkpoints"]
                            if r[1] or r[2]), None)
        cells.setdefault(name, {})[order] = {
            "receipt_sha256": sha(path), "workload_id": row["workload_id"],
            "branch_checkpoint": ready[0], "first_nonzero_ready_checkpoint": first_ready,
            "pair0_ready_branch_snapshots": ready[1],
            "pair1_ready_branch_snapshots": ready[2],
            "pair0_ready_with_free_mid_snapshots": ready[3],
            "pair1_ready_with_free_mid_snapshots": ready[4],
            "both_pairs_ready_snapshots": ready[5],
            "cnf_set_true_calls": work[1], "xor_set_true_calls": work[2],
            "combined_propagation_calls": work[1] + work[2],
            "log2_combined_propagation_calls_at_checkpoint": math.log2(
                work[1] + work[2]),
            "solver_wall_seconds_exploratory": row["solver_wall_seconds_exploratory"],
            "solver_user_cpu_seconds_exploratory": row[
                "solver_user_cpu_seconds_exploratory"]}
    comparisons = {}
    for name, pair in cells.items():
        old = pair["selector_pair_mids"]
        new = pair["q1478_leafpair_first"]
        comparisons[name] = {
            "cnf_calls_ratio_new_over_old": new["cnf_set_true_calls"] /
                                            old["cnf_set_true_calls"],
            "xor_calls_ratio_new_over_old": new["xor_set_true_calls"] /
                                            old["xor_set_true_calls"],
            "combined_calls_ratio_new_over_old": new["combined_propagation_calls"] /
                                                 old["combined_propagation_calls"],
            "new_ready_pair1_with_free_mid_per_million_combined_calls":
                1e6 * new["pair1_ready_with_free_mid_snapshots"] /
                new["combined_propagation_calls"],
            "completed_relation_cost_log2": None}
    result = {"proposal_id": "Q1478", "candidate_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol[
                  "factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
              "control_formula_replay": "PASS via validate.py",
              "frozen_input_sha256": sha(HERE / "freeze.json"),
              "drive_sha256": sha(HERE / "drive_receipt.json"),
              "analysis_source_sha256": sha(Path(__file__)),
              "cells": cells, "comparisons": comparisons,
              "root_query_unique_pair_count": None,
              "rootless_pair_rate": None,
              "natural_relation_yield": None,
              "novel_rank_per_query": None,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None,
              "degree131_challenge_gap_bits": None,
              "separate_conditional_n131_pair_index_counted_pair_additions_log2":
                  86.18470212672088,
              "separate_conditional_n131_pair_index_gap_pair_add_bits":
                  25.18470212672088}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    for name, comparison in comparisons.items():
        print(name, comparison["combined_calls_ratio_new_over_old"])


if __name__ == "__main__":
    main()
