#!/usr/bin/env python3
"""Q1498 independent duplicate-aware holdout for the selected 208-flip group."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1495 = PARENT / "q20261012_exact_rationality_filter"
Q1497 = PARENT / "q20261012_n83_restart_hyperparams"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def exact_usable(bits: str, filt, onb) -> bool:
    leaves = [int(bits[i:i+83][::-1], 2) for i in (0, 83)]
    return all(x and x.bit_count() <= 5 and filt.exact_predicate(onb, x)
               for x in leaves)


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    prior = read(Q1497 / "freeze.json")
    prior_build = read(Q1497 / "build_receipt.json")
    distinct = read(Q1497 / "distinct_analysis.json")
    assert distinct["duplicate_aware_selected_count"] == protocol["flip_count"]
    assert distinct["freeze_sha256"] == sha(Q1497 / "freeze.json")
    masks = {str(i): prior["mask_schedule"][str(i)] for i in protocol["phases"]}
    assert all(x["flip_count"] == protocol["flip_count"] for x in masks.values())
    assert prior["inputs"]["selected"]["workload_id"] == protocol[
        "selected_workload_id"]
    assert prior["inputs"]["holdout"]["workload_id"] == protocol[
        "holdout_workload_id"]
    binary = Path(prior_build["binary_path"])
    assert sha(binary) == prior_build["binary_sha256"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1498", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "q1491_sweep_sha256": sha(Q1491 / "sweep.py"),
        "q1495_filter_sha256": sha(Q1495 / "filter.py"),
        "q1497_freeze_sha256": sha(Q1497 / "freeze.json"),
        "q1497_build_receipt_sha256": sha(Q1497 / "build_receipt.json"),
        "q1497_distinct_analysis_sha256": sha(Q1497 / "distinct_analysis.json"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "inputs": prior["inputs"], "mask_schedule": masks,
        "selected_receipts_sha256": {str(i): sha(
            Q1497 / "runs" / f"selected_phase{i}" / "receipt.json")
            for i in protocol["phases"]},
    })
    print("Q1498 frozen", sha(HERE / "freeze.json")[:12])


def measure() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol, frozen = (read(HERE / n) for n in
                        ("protocol.json", "freeze.json"))
    assert sha(Path(__file__)) == frozen["source_sha256"]
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    prior_build = read(Q1497 / "build_receipt.json")
    assert sha(Q1497 / "build_receipt.json") == frozen[
        "q1497_build_receipt_sha256"]
    assert sha(Path(prior_build["binary_path"])) == frozen["binary_sha256"]
    sweep = module(Q1491 / "sweep.py", "q1491_sweep")
    filt = module(Q1495 / "filter.py", "q1495_filter")
    sweep.HERE = HERE
    onb = filt.CountedOnb(83)
    rows = []
    for phase in protocol["phases"]:
        row = sweep.run_cell("holdout", phase, protocol, frozen, prior_build)
        row["proposal_id"] = "Q1498"
        row["point_decomposition_stage_code"] = "PDP4sat"
        row["exact_usable_first_pair"] = (
            exact_usable(row["first_pair_bits"], filt, onb)
            if row["status"] == "FIRST_PAIR_TERMINATED" else None)
        folder = HERE / "runs" / f"holdout_phase{phase}"
        save(folder / "receipt.json", row)
        rows.append({"phase": phase, "receipt_sha256": sha(
            folder / "receipt.json")})
        print("Q1498 holdout", phase, row["status"],
              row["first_pair_combined_calls"],
              row["exact_usable_first_pair"], flush=True)
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1498", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })


def analyze() -> None:
    protocol, frozen, drive = (read(HERE / n) for n in
                               ("protocol.json", "freeze.json", "drive_receipt.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    assert sha(Q1497 / "distinct_analysis.json") == frozen[
        "q1497_distinct_analysis_sha256"]
    filt = module(Q1495 / "filter.py", "q1495_filter")
    onb = filt.CountedOnb(83)
    rows = []
    for entry in drive["rows"]:
        phase = entry["phase"]
        path = HERE / "runs" / f"holdout_phase{phase}" / "receipt.json"
        assert sha(path) == entry["receipt_sha256"]
        row = read(path)
        assert row["proposal_id"] == "Q1498" and row["candidate_id"] is None
        assert row["run_id"] is None and row["isogeny"] == "none"
        assert row["curve_id"] == protocol["curve_id"]
        assert row["workload_id"] == protocol["holdout_workload_id"]
        assert row["binary_sha256"] == frozen["binary_sha256"]
        assert sha(path.parent / "solver.stderr.txt") == row["stderr_sha256"]
        assert sha(path.parent / "solver.stdout.txt") == row["stdout_sha256"]
        if row["status"] == "FIRST_PAIR_TERMINATED":
            assert row["search_started"] and row["marker_ok"]
            assert row["exact_usable_first_pair"] == exact_usable(
                row["first_pair_bits"], filt, onb)
        rows.append(row)
    assert len(rows) == len(protocol["phases"])
    complete = all(x["status"] == "FIRST_PAIR_TERMINATED" for x in rows)
    usable = {x["first_pair_bits"] for x in rows
              if x["exact_usable_first_pair"] is True}
    calls = sum(x["first_pair_combined_calls"] or 0 for x in rows)
    prior = read(Q1497 / "distinct_analysis.json")
    result = {
        "proposal_id": "Q1498", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "selected_distinct_analysis_sha256": sha(Q1497 / "distinct_analysis.json"),
        "attempts": len(rows),
        "statuses": {s: sum(x["status"] == s for x in rows)
                     for s in sorted({x["status"] for x in rows})},
        "accepted_attempts": sum(x["exact_usable_first_pair"] is True
                                 for x in rows),
        "distinct_first_pairs": len({x["first_pair_bits"] for x in rows
                                     if x["first_pair_bits"] is not None}),
        "distinct_usable_pairs": len(usable),
        "charged_cnf_xor_calls": calls if complete else None,
        "calls_per_distinct_usable_pair": calls / len(usable)
        if complete and usable else None,
        "log2_calls_per_distinct_usable_pair": math.log2(calls / len(usable))
        if complete and usable else None,
        "selected_calls_per_distinct_usable_pair": prior[
            "selected_groups"]["208"]["calls_per_distinct_usable_pair"],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    save(HERE / "result.json", result)
    print("PASS Q1498", result["distinct_usable_pairs"],
          result["calls_per_distinct_usable_pair"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "measure", "analyze"):
        raise SystemExit("usage: holdout.py {freeze|measure|analyze}")
    globals()[sys.argv[1]]()
