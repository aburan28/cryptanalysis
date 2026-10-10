#!/usr/bin/env python3
"""Attach to the already launched positive worker after monitor preflight failed."""

import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(pid):
    case = "positive"
    protocol = json.loads((HERE / "protocol.json").read_text())
    attach = json.loads((HERE / "attach_protocol.json").read_text())
    assert attach["source_sha256"] == sha(Path(__file__))
    assert attach["protocol_sha256"] == sha(HERE / "protocol.json")
    assert pid == attach["worker_pid"]
    worker = psutil.Process(pid)
    assert abs(worker.create_time() - attach["worker_create_time_epoch"]) < 0.01
    process_start = worker.create_time()
    online_start_ns = None
    peak = 0
    stop = None
    while worker.is_running() and worker.status() != psutil.STATUS_ZOMBIE:
        try:
            peak = max(peak, worker.memory_info().rss + psutil.Process(os.getpid()).memory_info().rss)
        except psutil.NoSuchProcess:
            break
        progress_path = HERE / "progress.json"
        if progress_path.exists():
            try:
                progress = json.loads(progress_path.read_text())
                if progress.get("data", {}).get("case") == case:
                    online_ns = progress["data"].get("online_ns")
                    if online_ns is not None:
                        online_start_ns = int(progress["monotonic_ns"]) - int(online_ns)
            except (OSError, ValueError, KeyError):
                pass
        now = time.monotonic_ns()
        if peak >= protocol["rss_cap_bytes"]:
            stop = "RSS_CAP"
        elif time.time() - process_start >= protocol["process_wall_cap_seconds"]:
            stop = "PROCESS_WALL_CAP"
        elif online_start_ns is not None and now - online_start_ns >= protocol["online_wall_cap_seconds"]*10**9:
            stop = "ONLINE_WALL_CAP"
        if stop:
            worker.terminate()
            try:
                worker.wait(timeout=5)
            except psutil.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
                stop += "_KILLED"
            break
        time.sleep(0.1)
    result_path = HERE / "positive_result.json"
    receipt = {"status": "COMPLETE" if result_path.exists() and stop is None else
               "CENSORED_TIME" if stop in ("PROCESS_WALL_CAP", "ONLINE_WALL_CAP",
                                           "PROCESS_WALL_CAP_KILLED", "ONLINE_WALL_CAP_KILLED") else
               "MEMORY_CAP" if stop and stop.startswith("RSS_CAP") else "PRODUCER_FAILURE",
               "case": case, "candidate_id": None, "worker_pid": pid,
               "worker_create_time_epoch": process_start,
               "monitor_attached_after_worker_start": True,
               "online_clock_observed": online_start_ns is not None,
               "stop_reason": stop,
               "sampled_peak_combined_rss_bytes": peak,
               "result_sha256": sha(result_path) if result_path.exists() else None,
               "stdout_sha256": sha(HERE / "positive.stdout.txt"),
               "stderr_sha256": sha(HERE / "positive.stderr.txt"),
               "attach_protocol_sha256": sha(HERE / "attach_protocol.json")}
    path = HERE / "positive_attach_monitor.json"
    with path.open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: attach_monitor.py PID")
    main(int(sys.argv[1]))
