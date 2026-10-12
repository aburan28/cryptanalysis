#!/usr/bin/env python3
"""Verify Q1496 source, exact pair membership, receipts, and paired work."""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1491 = HERE.parent / "q20261012_n83_mask_density"
Q1494 = HERE.parent / "q20261012_n83_pair_base_audit"
Q1495 = HERE.parent / "q20261012_exact_rationality_filter"


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def run() -> None:
    build = module(HERE / "build.py", "q1496_build")
    sweep = module(Q1491 / "sweep.py", "q1491_sweep")
    filt = module(Q1495 / "filter.py", "q1495_filter")
    protocol, frozen, built, drive = (read(HERE / name) for name in
                                      ("protocol.json", "freeze.json",
                                       "build_receipt.json", "drive_receipt.json"))
    assert all(build.sha(HERE / name) == digest
               for name, digest in frozen["files_sha256"].items())
    assert built["freeze_sha256"] == drive["freeze_sha256"] == build.sha(
        HERE / "freeze.json")
    assert drive["build_receipt_sha256"] == build.sha(HERE / "build_receipt.json")
    assert build.sha(Path(built["binary_path"])) == built["binary_sha256"]
    assert build.sha(Path(built["guard_selftest_binary_path"])) == built[
        "guard_selftest_binary_sha256"]
    assert build.sha(Path(built["patched_source_path"])) == built[
        "patched_wdsat_c_sha256"]
    assert build.sha(Path(built["patched_source_path"]).parent / "makefile") == built[
        "patched_makefile_sha256"]
    assert build.sha(Path(frozen["parent_source_path"])) == frozen[
        "parent_source_sha256"]
    assert build.sha(Q1494 / "result.json") == frozen["q1494_result_sha256"]
    assert build.sha(Q1495 / "result.json") == frozen["q1495_result_sha256"]
    onb = filt.CountedOnb(83)
    rows = []
    for item in drive["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}"
        path = folder / "receipt.json"
        assert build.sha(path) == item["receipt_sha256"]
        row = read(path)
        assert row["proposal_id"] == "Q1496" and row["candidate_id"] is None
        assert row["run_id"] is None and row["isogeny"] == "none"
        assert row["curve_id"] == protocol["curve_id"]
        assert row["workload_id"] == frozen["inputs"][row["input"]]["workload_id"]
        assert row["phase"] == item["phase"]
        assert row["flip_count"] == protocol["flip_count"]
        assert row["binary_sha256"] == built["binary_sha256"]
        assert row["freeze_sha256"] == built["freeze_sha256"]
        assert build.sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert build.sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert row["search_started"] and row["marker_ok"]
        if row["guard_complete_checks"] is not None:
            assert row["guard_complete_checks"] == (row["guard_rejections"] +
                                                      row["guard_accepted_checks"])
        if row["status"] == "FIRST_PAIR_TERMINATED":
            bits = row["first_pair_bits"]
            assert bits and len(bits) == 166
            leaves = [int(bits[i:i+83][::-1], 2) for i in (0, 83)]
            assert all(x and x.bit_count() <= 5 and
                       filt.exact_predicate(onb, x) for x in leaves)
            native = subprocess.check_output(
                [built["guard_selftest_binary_path"], *(format(x, "x")
                                                      for x in leaves)],
                text=True).strip()
            assert native == "1"
            assert row["guard_accepted_checks"] >= 1
        elif row["status"] == "BRANCH_CAP_NO_USABLE_PAIR":
            assert row["return_code"] == 43 and not row["marker_seen"]
            assert row["guard_complete_checks"] is not None
        else:
            assert row["status"] in ("CPU_CAP_SEARCH_STARTED",
                                      "WALL_CAP_SEARCH_STARTED",
                                      "MODEL_REQUIRES_REPLAY", "PRODUCER_FAILURE")
        rows.append(row)
    assert len(rows) == 2 * len(protocol["phases"])
    assert {(r["input"], r["phase"]) for r in rows} == {
        (input_name, phase) for input_name in ("selected", "holdout")
        for phase in protocol["phases"]}
    summary = {}
    for input_name in ("selected", "holdout"):
        sub = [r for r in rows if r["input"] == input_name]
        baseline = [read(Q1491 / "runs" / f"{input_name}_phase{phase}" /
                         "receipt.json") for phase in protocol["phases"]]
        assert all(build.sha(Q1491 / "runs" / f"selected_phase{b['phase']}" /
                             "receipt.json") == frozen[
                                 "baseline_selected_receipts_sha256"][str(b["phase"])]
                   for b in baseline if input_name == "selected")
        complete = [r for r in sub if r["status"] == "FIRST_PAIR_TERMINATED"]
        statuses = {s: sum(r["status"] == s for r in sub)
                    for s in sorted({r["status"] for r in sub})}
        baseline_calls = sum(b["first_pair_combined_calls"] for b in baseline
                             if b["first_pair_combined_calls"] is not None)
        guarded_calls = sum(r["first_pair_combined_calls"] for r in complete)
        summary[input_name] = {
            "attempts": len(sub), "statuses": statuses,
            "usable_pairs": len(complete),
            "completed_combined_cnf_xor_calls": guarded_calls,
            "completed_calls_per_usable_pair":
                guarded_calls / len(complete) if len(complete) == len(sub)
                and complete else None,
            "baseline_first_pair_calls_sum": baseline_calls,
            "guard_complete_checks_sum": sum(r["guard_complete_checks"] or 0
                                             for r in sub),
            "guard_rejections_sum": sum(r["guard_rejections"] or 0
                                        for r in sub),
        }
    result = {
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "selected_workload_id": protocol["selected_workload_id"],
        "holdout_workload_id": protocol["holdout_workload_id"],
        "freeze_sha256": built["freeze_sha256"],
        "build_receipt_sha256": drive["build_receipt_sha256"],
        "drive_receipt_sha256": build.sha(HERE / "drive_receipt.json"),
        "summary": summary,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    build.save(HERE / "result.json", result)
    print("PASS Q1496", summary)


if __name__ == "__main__":
    run()
