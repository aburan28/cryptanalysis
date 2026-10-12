#!/usr/bin/env python3
"""Score root diversity and exact root outcomes for the Q1480 polarity grid."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1479 = HERE.parent / "q20261011_n83_distinct_roots"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_replay():
    spec = importlib.util.spec_from_file_location("q1479_analysis_for_q1480",
                                                  Q1479 / "analyze.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert sha(Q1479 / "analyze.py") == frozen["q1479_analyze_source_sha256"]
    replay = load_replay()
    onb = replay.CountedOnb(83)
    cells = {name: [] for name in ("selected", "holdout")}
    samples = {}
    for item in drive["rows"]:
        name, phase = item["input"], item["phase"]
        folder = HERE / "runs" / f"{name}_phase{phase}"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        log = (folder / "solver.stderr.txt").read_text()
        found = [(int(i), bits) for i, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert [i for i, _ in found] == list(range(1, len(found) + 1))
        assert len({bits for _, bits in found}) == len(found)
        root_rows = []
        for i, bits in found:
            root_rows.append({"sample_index": i, "leaf_bits": bits,
                              **replay.replay_pair(onb, bits)})
        samples[f"{name}_phase{phase}"] = root_rows
        rootless = sum(v["root_count"] == 0 for v in root_rows)
        root_entries = sum(v["field_api_entries"] for v in root_rows)
        work = row["work_at_cap"]
        complete = row["status"] == "CHECKPOINT_TERMINATED" and work is not None
        combined = work[1] + work[2] if work else None
        cell = {"input": name, "phase": phase, "status": row["status"],
                "workload_id": row["workload_id"],
                "branch_checkpoint": protocol["branch_checkpoint"] if complete else None,
                "distinct_pair1_count_sampled": len(root_rows),
                "rootless_pair_count_sampled": rootless,
                "root_count_distribution": {str(k): sum(v["root_count"] == k
                                                   for v in root_rows)
                                            for k in (0, 1, 2)},
                "sample_cap_reached": len(root_rows) == protocol[
                    "distinct_pair1_sample_cap_per_cell"],
                "overcap_snapshots_unclassified_uniqueness":
                    row["distinct_summary_at_cap"][3]
                    if row["distinct_summary_at_cap"] else None,
                "cnf_set_true_calls_at_cap": work[1] if work else None,
                "xor_set_true_calls_at_cap": work[2] if work else None,
                "combined_propagation_calls_at_cap": combined,
                "field_api_entries_sampled_root_queries": root_entries,
                "rootless_per_million_combined_calls":
                    1e6 * rootless / combined if combined else None,
                "distinct_per_million_combined_calls":
                    1e6 * len(root_rows) / combined if combined else None,
                "receipt_sha256": sha(row_path)}
        cells[name].append(cell)
    rankings = {}
    for name, rows in cells.items():
        finished = [r for r in rows if r["status"] == "CHECKPOINT_TERMINATED"]
        ordered = sorted(finished,
                         key=lambda r: (-r["rootless_per_million_combined_calls"],
                                        -r["distinct_per_million_combined_calls"],
                                        r["combined_propagation_calls_at_cap"],
                                        r["phase"]))
        rankings[name] = [r["phase"] for r in ordered]
    sample_path = HERE / "root_samples.json"
    sample_path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n")
    result = {"proposal_id": "Q1480", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol[
                  "factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
              "score": protocol["score"],
              "cells": cells, "pointwise_phase_rankings": rankings,
              "root_samples_sha256": sha(sample_path),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "drive_sha256": sha(HERE / "drive_receipt.json"),
              "analysis_source_sha256": sha(Path(__file__)),
              "ranking_scope": "pointwise fixed-prefix stage diagnostic; no population or complete-solve estimate",
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
    print("Q1480 rankings", rankings)


if __name__ == "__main__":
    main()
