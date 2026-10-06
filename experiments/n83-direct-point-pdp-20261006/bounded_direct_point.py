#!/usr/bin/env python3
"""Watch one N83 direct-point build and SAT process tree under a frozen cap."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import psutil
import signal
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
RUNNER = HERE / "run_direct_point_branch.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, record) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def sampled_tree(child: psutil.Process) -> tuple[int, float]:
    members = [psutil.Process(os.getpid())]
    try:
        members += [child, *child.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    rss, cpu = 0, 0.0
    for process in members:
        try:
            if process.is_running():
                rss += process.memory_info().rss
                clocks = process.cpu_times()
                cpu += clocks.user + clocks.system
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return rss, cpu


def main(mode: str, fiber_index: int, out: Path) -> int:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("direct-point output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert mode in ("pinned_planted", "unpinned_planted", "ordinary")
    assert fiber_index in range(4)
    out.mkdir(parents=True)
    argv = [sys.executable, str(RUNNER), mode, str(fiber_index), str(out)]
    save(out / "outer_started.json", {
        "kind": "bounded_n83_direct_point_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "mode": mode, "fiber_index": fiber_index,
        "protocol_sha256": sha(PROTOCOL),
        "runner_sha256": sha(RUNNER),
        "watchdog_sha256": sha(Path(__file__)),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started = time.perf_counter_ns()
    guard = None
    peak_rss, sampled_cpu = 0, 0.0
    stdout_path, stderr_path = out / "producer.stdout.txt", out / "producer.stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            rss, cpu = sampled_tree(root)
            peak_rss = max(peak_rss, rss)
            sampled_cpu = max(sampled_cpu, cpu)
            if peak_rss >= protocol["max_process_tree_rss_bytes"]:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - started) / 1e9 >= protocol["external_wall_seconds"]:
                guard = "external_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    inner_path = out / "receipt.json"
    inner = json.loads(inner_path.read_text()) if inner_path.is_file() else None
    status = ("INNER_COMPLETE" if guard is None and exit_code == 0 and inner
              else "RESOURCE_GUARD" if guard else "PRODUCER_FAILURE")
    report = {
        "schema_version": 1, "kind": "bounded_n83_direct_point_execution",
        "status": status, "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "mode": mode, "fiber_index": fiber_index,
        "argv": argv, "exit_code": exit_code, "guard": guard,
        "outer_wall_ns": time.perf_counter_ns() - started,
        "sampled_process_tree_cpu_seconds": sampled_cpu,
        "sampled_process_tree_peak_rss_bytes": peak_rss,
        "max_process_tree_rss_bytes": protocol["max_process_tree_rss_bytes"],
        "external_wall_seconds": protocol["external_wall_seconds"],
        "inner_receipt_sha256": sha(inner_path) if inner is not None else None,
        "inner_status": inner["status"] if inner is not None else None,
        "producer_stdout_sha256": sha(stdout_path),
        "producer_stderr_sha256": sha(stderr_path),
        "outer_started_sha256": sha(out / "outer_started.json"),
        "protocol_sha256": sha(PROTOCOL),
        "online_target_wall_ns": None,
        "rho_online_wall_ns": None,
        "online_speedup": None,
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "outer_receipt.json", report)
    print(json.dumps({"status": status, "inner_status": report["inner_status"],
                      "guard": guard, "outer_wall_seconds": report["outer_wall_ns"] / 1e9},
                     sort_keys=True), flush=True)
    return 0 if status == "INNER_COMPLETE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pinned_planted", "unpinned_planted", "ordinary"))
    parser.add_argument("fiber_index", type=int)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.mode, args.fiber_index, args.out))
