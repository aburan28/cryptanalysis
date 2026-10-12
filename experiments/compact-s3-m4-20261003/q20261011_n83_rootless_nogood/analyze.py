#!/usr/bin/env python3
"""Compare exact rootless nogood and phase-4 baseline in named work units."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q20261011_n83_leaf_masks"
Q1479 = PARENT / "q20261011_n83_distinct_roots"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root_replay():
    spec = importlib.util.spec_from_file_location("q1479_replay_for_q1482",
                                                  Q1479 / "analyze.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    replay = root_replay()
    onb = replay.CountedOnb(83)
    samples = {}
    points = {}
    for item in drive["rows"]:
        name, phase = item["input"], item["phase"]
        assert phase == 4
        folder = HERE / "runs" / f"{name}_phase4"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        log_path = folder / "solver.stderr.txt"
        assert sha(log_path) == row["stderr_sha256"]
        log = log_path.read_text()
        markers = [tuple(map(int, value)) for value in re.findall(
            r"^Q1482_NOGOOD (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
        at_cap = next((m for m in markers if m[0] == protocol[
            "branch_checkpoint"]), None)
        found = [(int(i), bits) for i, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert [i for i, _ in found] == list(range(1, len(found) + 1))
        entries = [{"sample_index": i, "leaf_bits": bits,
                    **replay.replay_pair(onb, bits)} for i, bits in found]
        samples[name] = entries
        base_path = Q1481 / "runs" / f"{name}_phase4" / "receipt.json"
        assert sha(base_path) == frozen["q1481_phase4_receipts_sha256"][name]
        base = json.loads(base_path.read_text())
        charged = row["work_at_cap"]
        baseline = base["work_at_cap"]
        ratio = ((charged[1] + charged[2]) / (baseline[1] + baseline[2])
                 if charged and baseline else None)
        points[name] = {
            "workload_id": row["workload_id"],
            "status": row["status"],
            "baseline_status": base["status"],
            "new_distinct_pair1_count_sampled": len(entries),
            "new_rootless_pair1_count_sampled": sum(x["root_count"] == 0
                                                    for x in entries),
            "new_root_query_field_api_entries_sampled": sum(
                x["field_api_entries"] for x in entries),
            "new_pair1_sample_cap_reached": len(entries) == protocol[
                "distinct_pair1_sample_cap_per_cell"],
            "baseline_distinct_pair1_count_sampled": base[
                "sampled_pair1_count"],
            "baseline_combined_cnf_xor_calls_at_cap":
                baseline[1] + baseline[2] if baseline else None,
            "new_combined_cnf_xor_calls_at_cap":
                charged[1] + charged[2] if charged else None,
            "new_over_baseline_combined_calls": ratio,
            "nogood_checks_at_cap": at_cap[1] if at_cap else None,
            "nogood_bit_tests_at_cap": at_cap[2] if at_cap else None,
            "nogood_rejections_at_cap": at_cap[3] if at_cap else None,
            "baseline_receipt_sha256": sha(base_path),
            "new_receipt_sha256": sha(row_path)}
    sample_path = HERE / "root_samples.json"
    sample_path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n")
    result = {"proposal_id": "Q1482", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol[
                  "factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
              "controlled_change": protocol["controlled_change"],
              "points": points,
              "root_samples_sha256": sha(sample_path),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "drive_sha256": sha(HERE / "drive_receipt.json"),
              "analysis_source_sha256": sha(Path(__file__)),
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
    print("Q1482", {name: (point["nogood_rejections_at_cap"],
                            point["new_distinct_pair1_count_sampled"],
                            point["new_over_baseline_combined_calls"])
                    for name, point in points.items()})


if __name__ == "__main__":
    main()
