#!/usr/bin/env python3
"""One-worker parent wall and process-tree RSS guard for the N41 Sage census."""

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
LAUNCHER = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_rss(process):
    try:
        return process.memory_info().rss
    except psutil.NoSuchProcess:
        return 0


def main():
    protocol = json.loads((HERE / "protocol_v2.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SAGE_REPLAY_V2"
    for name, path in {
        "run_sage_v2": Path(__file__),
        "sage_support_v2": HERE / "sage_support_v2.py",
        "sage_runtime_v2": HERE / "sage_runtime_info_v2.json",
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    folder = HERE / "sage_run_v2"
    folder.mkdir(exist_ok=False)
    stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
    result = HERE / "support_n41_v2.json"
    command = [str(LAUNCHER), "-python", str(HERE / "sage_support_v2.py")]
    started = time.monotonic_ns()
    peak = 0
    stop = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            peak = max(peak, process_rss(child))
            if peak > protocol["rss_cap_bytes"]:
                stop = "RSS_CAP"
            elif time.monotonic_ns() - started >= (
                    protocol["n41_cap_seconds"] * 10**9):
                stop = "WALL_CAP"
            if stop is not None:
                os.killpg(proc.pid, signal.SIGTERM)
                break
            time.sleep(0.05)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic_ns() - started
    if stop == "RSS_CAP":
        status = "OOM"
    elif stop is not None:
        status = "CENSORED_TIME"
    elif proc.returncode != 0 or not result.exists():
        status = "PRODUCER_FAILURE"
    else:
        payload = json.loads(result.read_text())
        status = payload["status"]
    receipt = {
        "status": status,
        "candidate_id": None,
        "target_count": 0,
        "command": command,
        "exit_code": proc.returncode,
        "stop_reason": stop,
        "parent_wall_ns": wall,
        "sampled_peak_process_tree_rss_bytes": peak,
        "source_sha256": {
            "protocol": sha(HERE / "protocol_v2.json"),
            "runtime": sha(HERE / "sage_runtime_info_v2.json"),
            "script": sha(HERE / "sage_support_v2.py"),
            "stdout": sha(stdout),
            "stderr": sha(stderr),
            "result": sha(result) if result.exists() else None,
        },
    }
    with (folder / "receipt.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "wall_s": wall / 1e9,
                      "peak_rss_bytes": peak}))


if __name__ == "__main__":
    main()
