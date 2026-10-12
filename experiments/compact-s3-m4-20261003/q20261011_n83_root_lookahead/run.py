#!/usr/bin/env python3
"""Run the root-lookahead control and two frozen ordinary inputs."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_one(label: str, protocol: dict, frozen: dict, build: dict) -> dict:
    out = HERE / "runs" / label
    assert not out.exists()
    out.mkdir(parents=True)
    source = Path(frozen["inputs"][label]["path"])
    assert sha(source) == frozen["inputs"][label]["sha256"]
    raw = source.read_bytes() if label == "control" else gzip.decompress(source.read_bytes())
    limits = protocol["limits"]
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE="selector_pair_mids", Q1472_PHASE_INDEX="0",
               Q1473_SELECTOR_PHASE="0")
    with tempfile.TemporaryDirectory(prefix="q1477_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        input_path = Path(tmp) / "system.xcnf"
        input_path.write_bytes(raw)
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        began = time.monotonic()
        try:
            process = subprocess.run([build["binary_path"], "-i", str(input_path)],
                                     env=env, capture_output=True,
                                     timeout=limits["wall_seconds_per_input"],
                                     preexec_fn=cpu_limit(limits[
                                         "cpu_soft_seconds_per_input"], limits[
                                         "cpu_hard_seconds_per_input"]))
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
            timed_out = True
        wall = time.monotonic() - began
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path, stderr_path = out / "solver.stdout.txt", out / "solver.stderr.txt"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    text = stderr.decode("ascii", "replace")
    matches = re.findall(r"^Q1477_ROOT (-?\d+) ([01]) (\d+) (\d+) (\d+) (\d+)$",
                         text, re.M)
    rows = [{"literal": int(row[0]), "consistent": bool(int(row[1])),
             "cnf_calls": int(row[2]), "xor_calls": int(row[3]),
             "cnf_new_assignments": int(row[4]),
             "xor_new_assignments": int(row[5])} for row in matches]
    restored = re.findall(r"^Q1477_ROOT_RESTORED (\d+) (\d+)$", text, re.M)
    marker_ok = (text.splitlines().count("Q1469_ORDER selector_pair_mids 168") == 1 and
                 text.splitlines().count("Q1472_PHASE 0 0") == 1 and
                 text.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1)
    if (not timed_out and code == 43 and marker_ok and
            [row["literal"] for row in rows] == protocol["probe_literals"] and
            len(restored) == 1 and "Q1477_RESTORE_FAILURE" not in text and
            "Q1458_SEARCH_START" not in text):
        status = "ROOT_PROBES_RESTORED"
    elif timed_out:
        status = "WALL_CAP_BEFORE_ROOT_PROBES"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL):
        status = "CPU_CAP_BEFORE_ROOT_PROBES"
    else:
        status = "PRODUCER_FAILURE"
    receipt = {
        "proposal_id": "Q1477", "candidate_id": None, "run_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "workload_id": frozen["inputs"][label]["workload_id"],
        "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "status": status, "return_code": code, "timed_out": timed_out,
        "marker_ok": marker_ok, "root_rows": rows,
        "restored_cnf_xor_assignment_counts": ([int(v) for v in restored[0]]
                                               if restored else None),
        "search_started": "Q1458_SEARCH_START" in text,
        "q1473_final_work_rows": [list(map(int, match)) for match in re.findall(
            r"^Q1473_WORK_FINAL (\d+) (\d+)$", text, re.M)],
        "solver_wall_seconds_exploratory": wall,
        "user_cpu_seconds_exploratory": after.ru_utime - before.ru_utime,
        "system_cpu_seconds_exploratory": after.ru_stime - before.ru_stime,
        "maxrss_children_cumulative_bytes_darwin": after.ru_maxrss,
        "input_sha256": sha(source), "raw_input_sha256": hashlib.sha256(raw).hexdigest(),
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "binary_sha256": build["binary_sha256"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "source_sha256": sha(Path(__file__)),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                 sort_keys=True) + "\n")
    return receipt


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    rows = []
    for label in ("control", "selected", "holdout"):
        row = run_one(label, protocol, frozen, build)
        rows.append(row)
        print("Q1477", label, row["status"], row["root_rows"], flush=True)
        if row["status"] != "ROOT_PROBES_RESTORED":
            break
    drive = {"proposal_id": "Q1477", "status": "COMPLETE_SCHEDULE" if
             len(rows) == 3 else "STOPPED_AT_GATE",
             "labels": [row["label"] for row in rows],
             "statuses": [row["status"] for row in rows],
             "total_exploratory_solver_wall_seconds": sum(
                 row["solver_wall_seconds_exploratory"] for row in rows),
             "total_exploratory_user_cpu_seconds": sum(
                 row["user_cpu_seconds_exploratory"] for row in rows),
             "freeze_sha256": sha(HERE / "freeze.json"),
             "complete_n83_decomposition_work_log2": None,
             "complete_n131_solve_work_log2": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(drive, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
