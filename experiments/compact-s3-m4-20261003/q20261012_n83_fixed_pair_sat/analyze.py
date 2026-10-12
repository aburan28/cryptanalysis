#!/usr/bin/env python3
"""Validate fixed-pair SAT cap rows and compare frozen mask choices."""
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1499 = PARENT / "q20261012_n83_full_continuation_pilot"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol, frozen, result = (read(HERE / n) for n in
                                ("protocol.json", "freeze.json", "result.json"))
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    assert sha(HERE / "run.py") == frozen["source_sha256"]
    assert sha(HERE / "freeze.json") == result["freeze_sha256"]
    assert len(result["rows"]) == 6
    rows = []
    for row in result["rows"]:
        label, phase = row["input"], row["phase"]
        folder = HERE / "runs" / f"{label}_phase{phase}"
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert sha(folder / "receipt.json")
        assert row["status"] == "BRANCH_CAP_SEARCH_STARTED"
        assert row["return_code"] == 42 and row["search_started"]
        assert row["first_pair_marker_count"] == 1
        log = (folder / "solver.stderr.txt").read_text()
        first = re.search(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$",
                          log, re.M)
        assert first and first.group(4) == frozen["inputs"][label]["first_pair_bits"]
        assert int(first.group(1)) == 1
        ready = re.findall(r"^Q1478_READY (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$",
                           log, re.M)
        pair0, pair1, early0, early1, both = map(int, ready[-1][1:])
        assert int(ready[-1][0]) == 1048576
        assert pair1 == 1048576 and pair0 == both and both >= 1048555
        calls = sum(row["last_checkpoint"][1:])
        assert row["last_checkpoint"][0] == 1048576
        rows.append({"input": label, "phase": phase,
                     "flip_count": 208, "status": row["status"],
                     "first_pair_branch": int(first.group(1)),
                     "first_pair_cnf_xor_calls": int(first.group(2)) + int(first.group(3)),
                     "branch_cap": 1048576, "cnf_xor_calls_at_cap": calls,
                     "both_leaf_pairs_fully_assigned_snapshots": both,
                     "both_leaf_pairs_fully_assigned_fraction": both / 1048576,
                     "pair0_full_snapshots": pair0,
                     "pair1_full_snapshots": pair1,
                     "early0_snapshots": early0,
                     "early1_snapshots": early1})
    phase50 = next(r for r in rows if r["input"] == "selected" and r["phase"] == 50)
    phase51 = next(r for r in rows if r["input"] == "selected" and r["phase"] == 51)
    original = read(Q1499 / "runs/selected_phase50/receipt.json")
    assert original["status"] == "BRANCH_CAP_SEARCH_STARTED"
    analysis = {"proposal_id": "Q1503", "candidate_id": None, "run_id": None,
                "curve_id": protocol["curve_id"], "isogeny": "none",
                "point_decomposition_stage_code": "PDP4sat",
                "freeze_sha256": sha(HERE / "freeze.json"),
                "result_sha256": sha(HERE / "result.json"),
                "q1499_selected_phase50_receipt_sha256":
                sha(Q1499 / "runs/selected_phase50/receipt.json"),
                "rows": rows,
                "selected_phase51_calls_relative_to_phase50":
                phase51["cnf_xor_calls_at_cap"] / phase50["cnf_xor_calls_at_cap"],
                "selected_phase51_lower_cap_work_log2_bits":
                math.log2(phase50["cnf_xor_calls_at_cap"] /
                          phase51["cnf_xor_calls_at_cap"]),
                "selected_fixed_phase50_extra_calls_vs_unfixed_phase50":
                phase50["cnf_xor_calls_at_cap"] -
                original["last_checkpoint_combined_calls"],
                "complete_n83_decomposition_work_log2": None,
                "complete_n131_solve_work_log2": None}
    (HERE / "analysis.json").write_text(json.dumps(
        analysis, indent=2, sort_keys=True) + "\n")
    print("PASS Q1503", analysis["selected_phase51_lower_cap_work_log2_bits"])


if __name__ == "__main__":
    main()
