#!/usr/bin/env python3
"""Enforce one-worker N41 batch-GCD wall and process-tree RSS limits."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
PROTOCOL = HERE / "protocol.json"
MONITOR_PROTOCOL = HERE / "monitor_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def rss_tree(pid):
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return 0
    total = 0
    for process in processes:
        try:
            total += process.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return total


def main(case):
    if case not in ("positive", "public"):
        raise ValueError(case)
    protocol = json.loads(PROTOCOL.read_text())
    monitor_protocol = json.loads(MONITOR_PROTOCOL.read_text())
    assert monitor_protocol["monitor_sha256"] == sha(Path(__file__))
    assert monitor_protocol["protocol_sha256"] == sha(PROTOCOL)
    result_path = HERE / f"{case}_result.json"
    receipt_path = HERE / f"{case}_monitor.json"
    if receipt_path.exists() or result_path.exists():
        raise FileExistsError("case already has output")
    stdout_path = HERE / f"{case}.stdout.txt"
    stderr_path = HERE / f"{case}.stderr.txt"
    command = [str(SAGE), "-python", str(HERE / "batch.py"), case]
    began = time.monotonic_ns()
    online_start_ns = None
    peak = 0
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        proc = subprocess.Popen(command, cwd=HERE, stdout=stdout, stderr=stderr,
                                start_new_session=True)
        while proc.poll() is None:
            peak = max(peak, rss_tree(os.getpid()))
            progress_path = HERE / "progress.json"
            if online_start_ns is None and progress_path.exists():
                try:
                    progress = json.loads(progress_path.read_text())
                    stamp = int(progress["monotonic_ns"])
                    if stamp >= began and (progress.get("phase") == "reusable_setup" or
                                           progress.get("data", {}).get("case") == case):
                        online_start_ns = stamp
                except (OSError, ValueError, KeyError):
                    pass
            now = time.monotonic_ns()
            if peak >= protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
            elif now - began >= protocol["process_wall_cap_seconds"]*10**9:
                stop_reason = "PROCESS_WALL_CAP"
            elif online_start_ns is not None and now - online_start_ns >= protocol["online_wall_cap_seconds"]*10**9:
                stop_reason = "ONLINE_WALL_CAP"
            if stop_reason:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    stop_reason += "_KILLED"
                break
            time.sleep(0.1)
        proc.wait()
    elapsed_ns = time.monotonic_ns() - began
    status = "COMPLETE" if proc.returncode == 0 and result_path.exists() else (
        "CENSORED_TIME" if stop_reason in ("ONLINE_WALL_CAP", "PROCESS_WALL_CAP",
                                      "ONLINE_WALL_CAP_KILLED", "PROCESS_WALL_CAP_KILLED")
        else "MEMORY_CAP" if stop_reason and stop_reason.startswith("RSS_CAP")
        else "PRODUCER_FAILURE")
    receipt = {"status": status, "case": case, "candidate_id": None,
               "command": command, "exit_code": proc.returncode,
               "stop_reason": stop_reason, "process_wall_ns": elapsed_ns,
               "online_clock_observed": online_start_ns is not None,
               "sampled_peak_process_tree_rss_bytes": peak,
               "worker_result_sha256": sha(result_path) if result_path.exists() else None,
               "progress_sha256": sha(HERE / "progress.json") if (HERE / "progress.json").exists() else None,
               "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
               "monitor_protocol_sha256": sha(MONITOR_PROTOCOL)}
    save(receipt_path, receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: monitor.py positive|public")
    main(sys.argv[1])
