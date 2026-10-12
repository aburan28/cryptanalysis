#!/usr/bin/env python3
"""Frozen bounded full-chain WDSat continuation on four ordinary N83 cells."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1497 = PARENT / "q20261012_n83_restart_hyperparams"
Q1498 = PARENT / "q20261012_n83_distinct_restart_holdout"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    sweep = read(Q1497 / "freeze.json")
    build = read(Q1497 / "build_receipt.json")
    distinct = read(Q1497 / "distinct_analysis.json")
    assert distinct["duplicate_aware_selected_count"] == 208
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert [sweep["mask_schedule"][str(i)]["flip_count"] for i in
            protocol["phases"]] == [208, 208]
    first_pair_receipts = {}
    for input_name in ("selected", "holdout"):
        assert sweep["inputs"][input_name]["workload_id"] == protocol[
            f"{input_name}_workload_id"]
        for phase in protocol["phases"]:
            folder = Q1497 if input_name == "selected" else Q1498
            path = folder / "runs" / f"{input_name}_phase{phase}" / "receipt.json"
            row = read(path)
            assert row["status"] == "FIRST_PAIR_TERMINATED"
            assert row["exact_usable_first_pair"] == (phase == 50)
            first_pair_receipts[f"{input_name}_{phase}"] = {
                "path": str(path), "sha256": sha(path),
                "first_pair_bits": row["first_pair_bits"],
                "first_pair_combined_calls": row["first_pair_combined_calls"],
            }
    save(HERE / "freeze.json", {
        "proposal_id": "Q1499", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "q1497_freeze_sha256": sha(Q1497 / "freeze.json"),
        "q1497_build_receipt_sha256": sha(Q1497 / "build_receipt.json"),
        "q1497_distinct_analysis_sha256": sha(Q1497 / "distinct_analysis.json"),
        "q1498_result_sha256": sha(Q1498 / "result.json"),
        "binary_path": build["binary_path"],
        "binary_sha256": build["binary_sha256"],
        "inputs": sweep["inputs"],
        "mask_schedule": {str(i): sweep["mask_schedule"][str(i)]
                          for i in protocol["phases"]},
        "first_pair_receipts": first_pair_receipts,
    })
    print("Q1499 frozen", sha(HERE / "freeze.json")[:12])


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol, frozen = (read(HERE / n) for n in
                        ("protocol.json", "freeze.json"))
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    assert sha(Path(__file__)) == frozen["source_sha256"]
    binary = Path(frozen["binary_path"])
    assert sha(binary) == frozen["binary_sha256"]
    rows = []
    for input_name in ("selected", "holdout"):
        cell = frozen["inputs"][input_name]
        archive = Path(cell["derived_path"])
        assert sha(archive) == cell["derived_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        for phase in protocol["phases"]:
            folder = HERE / "runs" / f"{input_name}_phase{phase}"
            assert not folder.exists()
            folder.mkdir(parents=True)
            env = os.environ.copy()
            env.update(Q1469_ORDER_MODE=protocol["branch_order"],
                       Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
                       Q1481_LEAF_MASK=str(phase))
            started = time.monotonic()
            usage0 = resource.getrusage(resource.RUSAGE_CHILDREN)
            with tempfile.TemporaryDirectory(prefix="q1499_",
                                             dir="/Volumes/SSD990/llm/tmp") as tmp:
                system = Path(tmp) / "system.xcnf"
                system.write_bytes(raw)
                command = [str(binary), "-i", str(system)]
                try:
                    process = subprocess.run(
                        command, env=env, capture_output=True,
                        timeout=protocol["wall_seconds_per_cell"],
                        preexec_fn=cpu_limit(
                            protocol["cpu_soft_seconds_per_cell"],
                            protocol["cpu_hard_seconds_per_cell"]))
                    stdout, stderr = process.stdout, process.stderr
                    code, wall_cap = process.returncode, False
                except subprocess.TimeoutExpired as error:
                    stdout, stderr = error.stdout or b"", error.stderr or b""
                    code, wall_cap = None, True
            elapsed = time.monotonic() - started
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            out = folder / "solver.stdout.txt"
            err = folder / "solver.stderr.txt"
            out.write_bytes(stdout)
            err.write_bytes(stderr)
            log = stderr.decode("utf8", "replace")
            checkpoints = [(int(a), int(b), int(c)) for a, b, c in
                           re.findall(r"^Q1473_WORK (\d+) (\d+) (\d+)$",
                                      log, re.M)]
            first = re.findall(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$",
                               log, re.M)
            assert len(first) <= 1
            search_started = "Q1458_SEARCH_START" in log
            marker_ok = all(x in log for x in (
                f"Q1469_ORDER {protocol['branch_order']} 168",
                "Q1472_PHASE 0 0", "Q1473_SELECTOR_PHASE 0 2140 2141",
                f"Q1481_MASK {phase} 208"))
            if first:
                prior = frozen["first_pair_receipts"][f"{input_name}_{phase}"]
                assert sha(Path(prior["path"])) == prior["sha256"]
                assert first[0][3] == prior["first_pair_bits"]
                assert int(first[0][1]) + int(first[0][2]) == prior[
                    "first_pair_combined_calls"]
            if wall_cap and search_started:
                status = "WALL_CAP_SEARCH_STARTED"
            elif code in (-signal.SIGXCPU, -signal.SIGKILL) and search_started:
                status = "CPU_CAP_SEARCH_STARTED"
            elif code == 42 and search_started and "Q1464_BRANCH_CAP" in log:
                status = "BRANCH_CAP_SEARCH_STARTED"
            elif code == 0 and b"UNSAT" in stdout:
                status = "UNSAT_REPORTED_UNVERIFIED"
            elif code == 0 and stdout:
                status = "SOLVER_OUTPUT_REQUIRES_REPLAY"
            elif code == 0:
                status = "NO_MODEL_REPORTED"
            elif not search_started:
                status = "PRODUCER_FAILURE_BEFORE_SEARCH"
            else:
                status = "PRODUCER_FAILURE_SEARCH_STARTED"
            row = {
                "proposal_id": "Q1499", "candidate_id": None, "run_id": None,
                "curve_id": protocol["curve_id"], "isogeny": "none",
                "point_decomposition_stage_code": "PDP4sat",
                "workload_id": cell["workload_id"],
                "factor_base_actual_B": protocol["factor_base_actual_B"],
                "factor_base_folded_columns_K": protocol[
                    "factor_base_folded_columns_K"],
                "input": input_name, "phase": phase,
                "first_pair_exact_usable": phase == 50,
                "first_pair_seen": bool(first),
                "first_pair_branch": int(first[0][0]) if first else None,
                "search_started": search_started, "marker_ok": marker_ok,
                "status": status, "return_code": code, "wall_cap": wall_cap,
                "last_checkpoint_branch": checkpoints[-1][0] if checkpoints else None,
                "last_checkpoint_cnf_calls": checkpoints[-1][1] if checkpoints else None,
                "last_checkpoint_xor_calls": checkpoints[-1][2] if checkpoints else None,
                "last_checkpoint_combined_calls":
                    checkpoints[-1][1] + checkpoints[-1][2] if checkpoints else None,
                "solver_wall_seconds_exploratory": elapsed,
                "solver_user_cpu_seconds_exploratory":
                    usage.ru_utime - usage0.ru_utime,
                "solver_system_cpu_seconds_exploratory":
                    usage.ru_stime - usage0.ru_stime,
                "child_peak_rss_cumulative_bytes_darwin": usage.ru_maxrss,
                "stdout_sha256": sha(out), "stderr_sha256": sha(err),
                "binary_sha256": frozen["binary_sha256"],
                "input_sha256": cell["derived_sha256"],
                "freeze_sha256": sha(HERE / "freeze.json"),
                "complete_n83_decomposition_work_log2": None,
                "complete_n131_solve_work_log2": None,
            }
            save(folder / "receipt.json", row)
            rows.append({"input": input_name, "phase": phase,
                         "receipt_sha256": sha(folder / "receipt.json")})
            print("Q1499", input_name, phase, status,
                  row["last_checkpoint_combined_calls"], flush=True)
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1499", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"), "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })


def analyze() -> None:
    protocol, frozen, drive = (read(HERE / n) for n in
                               ("protocol.json", "freeze.json", "drive_receipt.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    rows = []
    for item in drive["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}"
        path = folder / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = read(path)
        assert row["search_started"] and row["marker_ok"] and row["first_pair_seen"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert row["binary_sha256"] == frozen["binary_sha256"]
        rows.append(row)
    assert len(rows) == 2 * len(protocol["phases"])
    statuses = {s: sum(x["status"] == s for x in rows)
                for s in sorted({x["status"] for x in rows})}
    result = {
        "proposal_id": "Q1499", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "statuses": statuses,
        "min_last_checkpoint_combined_calls": min(
            x["last_checkpoint_combined_calls"] for x in rows),
        "max_last_checkpoint_combined_calls": max(
            x["last_checkpoint_combined_calls"] for x in rows),
        "rows": [{"input": x["input"], "phase": x["phase"],
                  "status": x["status"],
                  "last_checkpoint_branch": x["last_checkpoint_branch"],
                  "last_checkpoint_combined_calls":
                      x["last_checkpoint_combined_calls"],
                  "solver_wall_seconds_exploratory":
                      x["solver_wall_seconds_exploratory"]}
                 for x in rows],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    save(HERE / "result.json", result)
    print("PASS Q1499", statuses, result[
        "min_last_checkpoint_combined_calls"], result[
            "max_last_checkpoint_combined_calls"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run", "analyze"):
        raise SystemExit("usage: pilot.py {freeze|run|analyze}")
    globals()[sys.argv[1]]()
