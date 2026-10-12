#!/usr/bin/env python3
"""Q1500 full-cap distinct first-pair exposure in ordinary N83 WDSat."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1497 = PARENT / "q20261012_n83_restart_hyperparams"
Q1498 = PARENT / "q20261012_n83_distinct_restart_holdout"
Q1499 = PARENT / "q20261012_n83_full_continuation_pilot"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1500_full_pair_exposure_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def parent_module():
    path = Q1499 / "pilot.py"
    spec = importlib.util.spec_from_file_location("q1499_pilot", path)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    prior = read(Q1499 / "freeze.json")
    source = Path(read(Q1497 / "build_receipt.json")["patched_source_path"])
    assert sha(source) == read(Q1497 / "build_receipt.json")[
        "patched_source_sha256"]
    pairs = {f"{name}_50": prior["first_pair_receipts"][f"{name}_50"]
             for name in ("selected", "holdout")}
    for name in ("selected", "holdout"):
        assert prior["inputs"][name]["workload_id"] == protocol[
            f"{name}_workload_id"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1500", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "experiment_source_sha256": sha(Path(__file__)),
        "source_sha256": sha(Q1499 / "pilot.py"),
        "q1499_freeze_sha256": sha(Q1499 / "freeze.json"),
        "q1497_build_receipt_sha256": sha(Q1497 / "build_receipt.json"),
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "inputs": prior["inputs"],
        "mask_schedule": {"50": prior["mask_schedule"]["50"]},
        "first_pair_receipts": pairs,
        "binary_path": None, "binary_sha256": None,
    })
    print("Q1500 frozen", sha(HERE / "freeze.json")[:12])


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = read(HERE / "freeze.json")
    assert sha(Path(__file__)) == frozen["experiment_source_sha256"]
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    path = BUILD / "src/wdsat.c"
    data = path.read_text()
    old = "    if (count >= 32768) q1479_capture_enabled = false;"
    assert data.count(old) == 1
    data = data.replace(old, "    /* Q1500: retain exact pair capture through branch cap. */")
    path.write_text(data)
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1500", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "patched_source_path": str(path),
        "patched_source_sha256": sha(path),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "config_sha256": sha(BUILD / "src/config.h"),
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
    })
    print("Q1500 built", sha(binary)[:12])


def run() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    frozen = read(HERE / "freeze.json")
    built = read(HERE / "build_receipt.json")
    assert sha(HERE / "freeze.json") == built["freeze_sha256"]
    assert sha(Path(built["binary_path"])) == built["binary_sha256"]
    # Q1499's source-bound runner has the identical input and limit contract.
    # Supply the Q1500 binary in memory; leave the frozen Q1500 file untouched.
    prior = parent_module()
    prior.HERE = HERE
    original_read = prior.read
    def read_with_binary(path: Path):
        obj = original_read(path)
        if path == HERE / "freeze.json":
            obj["binary_path"] = built["binary_path"]
            obj["binary_sha256"] = built["binary_sha256"]
        return obj
    prior.read = read_with_binary
    prior.run()
    drive = read(HERE / "drive_receipt.json")
    for item in drive["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}"
        row = read(folder / "receipt.json")
        row["proposal_id"] = "Q1500"
        row["binary_sha256"] = built["binary_sha256"]
        save(folder / "receipt.json", row)
        item["receipt_sha256"] = sha(folder / "receipt.json")
    drive["proposal_id"] = "Q1500"
    drive["build_receipt_sha256"] = sha(HERE / "build_receipt.json")
    save(HERE / "drive_receipt.json", drive)


def analyze() -> None:
    protocol, frozen, built, drive = (read(HERE / n) for n in
                                      ("protocol.json", "freeze.json",
                                       "build_receipt.json", "drive_receipt.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    assert sha(HERE / "build_receipt.json") == drive["build_receipt_sha256"]
    assert len(drive["rows"]) == 2
    rows = []
    for item in drive["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}"
        path = folder / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = read(path)
        assert row["proposal_id"] == "Q1500" and row["candidate_id"] is None
        assert row["status"] == "BRANCH_CAP_SEARCH_STARTED"
        assert row["last_checkpoint_branch"] == 1048576
        assert row["search_started"] and row["marker_ok"]
        assert row["binary_sha256"] == built["binary_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        log = (folder / "solver.stderr.txt").read_text()
        summaries = [(int(a), int(b), int(c), int(d)) for a, b, c, d in
                     re.findall(r"^Q1479_SUMMARY (\d+) (\d+) (\d+) (\d+)$",
                                log, re.M)]
        assert summaries and summaries[-1][0] == 1048576
        captured = re.findall(r"^Q1479_PAIR1 \d+ ([01]{166})$", log, re.M)
        assert len(captured) == summaries[-1][1]
        assert len(set(captured)) == len(captured)
        rows.append({"input": row["input"], "phase": row["phase"],
                     "status": row["status"],
                     "branch_cap": summaries[-1][0],
                     "distinct_first_pairs_captured": summaries[-1][1],
                     "duplicate_pair_snapshots": summaries[-1][2],
                     "capture_overflow": summaries[-1][3],
                     "last_checkpoint_combined_calls":
                         row["last_checkpoint_combined_calls"],
                     "solver_wall_seconds_exploratory":
                         row["solver_wall_seconds_exploratory"]})
    save(HERE / "result.json", {
        "proposal_id": "Q1500", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("PASS Q1500", rows)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "build", "run", "analyze"):
        raise SystemExit("usage: experiment.py {freeze|build|run|analyze}")
    globals()[sys.argv[1]]()
