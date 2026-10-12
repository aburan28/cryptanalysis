#!/usr/bin/env python3
"""Correct Q1497's duplicate-sensitive accepted-pair objective."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1491 = HERE.parent / "q20261012_n83_mask_density"
Q1494 = HERE.parent / "q20261012_n83_pair_base_audit"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def run() -> None:
    protocol, frozen, drive, result = (read(HERE / n) for n in
                                      ("protocol.json", "freeze.json",
                                       "drive_receipt.json", "result.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    assert sha(HERE / "drive_receipt.json") == result["drive_receipt_sha256"]
    assert sha(Q1494 / "result.json") == frozen["q1494_result_sha256"]
    groups = {}
    for count in protocol["flip_counts"]:
        phases = [int(k) for k, v in frozen["mask_schedule"].items()
                  if v["flip_count"] == count]
        rows = []
        for phase in phases:
            folder = HERE / "runs" / f"selected_phase{phase}"
            path = folder / "receipt.json"
            entry = next(x for x in drive["rows"] if x["input"] == "selected"
                         and x["phase"] == phase)
            assert sha(path) == entry["receipt_sha256"]
            row = read(path)
            assert row["status"] == "FIRST_PAIR_TERMINATED"
            assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
            rows.append(row)
        all_pairs = {x["first_pair_bits"] for x in rows}
        usable = {x["first_pair_bits"] for x in rows
                  if x["exact_usable_first_pair"]}
        calls = sum(x["first_pair_combined_calls"] for x in rows)
        groups[str(count)] = {
            "attempts": len(rows), "accepted_attempts": sum(
                x["exact_usable_first_pair"] for x in rows),
            "distinct_pairs": len(all_pairs),
            "distinct_usable_pairs": len(usable),
            "charged_cnf_xor_calls": calls,
            "calls_per_distinct_usable_pair": calls / len(usable)
            if usable else None,
            "log2_calls_per_distinct_usable_pair": math.log2(calls / len(usable))
            if usable else None,
        }
    rank = sorted((v["calls_per_distinct_usable_pair"], int(k))
                  for k, v in groups.items()
                  if v["calls_per_distinct_usable_pair"] is not None)
    assert rank[0][1] == 208
    baseline = read(Q1494 / "result.json")
    prior_phases = range(41, 49)
    prior_usable = {r["phase"] for r in baseline["rows"]
                    if r["phase"] in prior_phases and r["both_usable"]}
    assert prior_usable == {41, 45, 48}
    prior_calls = sum(read(Q1491 / "runs" / f"selected_phase{i}" /
                           "receipt.json")["first_pair_combined_calls"]
                      for i in prior_phases)
    assert prior_calls == 778598
    selected = groups["208"]["calls_per_distinct_usable_pair"]
    output = {
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "result_sha256": sha(HERE / "result.json"),
        "analysis_source_sha256": sha(Path(__file__)),
        "selected_groups": groups,
        "duplicate_aware_selected_count": 208,
        "prior_q1491_249_calls_per_distinct_usable_pair":
            prior_calls / len(prior_usable),
        "q1497_208_calls_per_distinct_usable_pair": selected,
        "relative_calls_208_to_prior_249": selected / (prior_calls / len(prior_usable)),
        "improvement_log2_bits": math.log2((prior_calls / len(prior_usable)) /
                                           selected),
        "note": "The original selected_count=331 used accepted attempts and counted eight repetitions of one pair. This versioned analysis selects by distinct usable pair and leaves the original receipts unchanged.",
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    (HERE / "distinct_analysis.json").write_text(json.dumps(
        output, indent=2, sort_keys=True) + "\n")
    print("PASS Q1497 distinct", rank, output["improvement_log2_bits"])


if __name__ == "__main__":
    run()
