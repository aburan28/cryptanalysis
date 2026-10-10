#!/usr/bin/env python3
"""Parent wall/RSS supervisor for the frozen native four-atom oracle."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(n, kind):
    protocol = json.loads((HERE / "native_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_NATIVE_FOUR_ATOM_PANEL"
    for name, path in {"runner": Path(__file__), "native_source": HERE / "native.cpp",
                       "native_binary": HERE / "native",
                       "terms_header": HERE / "resultant_terms.hpp",
                       f"native_input_n{n}_{kind}": HERE / f"native_n{n}_{kind}.txt"}.items():
        assert protocol["source_sha256"][name] == sha(path), name
    folder = HERE / f"native_run_n{n}_{kind}"
    folder.mkdir(exist_ok=False)
    source = HERE / f"native_n{n}_{kind}.txt"
    result = folder / "result.json"
    stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
    cap = protocol["parent_caps_seconds"][str(n)]
    inner = protocol["internal_caps_seconds"][str(n)]
    command = [str(HERE / "native"), str(source), str(result), str(inner),
               str(protocol["rss_cap_bytes"])]
    start = time.monotonic_ns()
    peak = 0
    stop = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak = max(peak, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak > protocol["rss_cap_bytes"]:
                stop = "PARENT_RSS_CAP"
            elif time.monotonic_ns() - start >= cap * 10**9:
                stop = "PARENT_WALL_CAP"
            if stop:
                proc.terminate()
                break
            time.sleep(0.05)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic_ns() - start
    producer = json.loads(result.read_text()) if result.exists() else None
    if stop and "RSS" in stop:
        status = "OOM"
    elif stop:
        status = "CENSORED_TIME"
    elif proc.returncode != 0 or producer is None:
        status = "PRODUCER_FAILURE"
    else:
        status = producer["status"]
    receipt = {
        "status": status, "field_degree": n, "case": kind,
        "candidate_id": None, "target_count": 0,
        "command": command, "exit_code": proc.returncode,
        "stop_reason": stop, "parent_wall_ns": wall,
        "sampled_peak_rss_bytes": peak,
        "producer_status": producer["status"] if producer else None,
        "source_sha256": {"protocol": sha(HERE / "native_protocol.json"),
                          "input": sha(source), "binary": sha(HERE / "native"),
                          "stdout": sha(stdout), "stderr": sha(stderr),
                          "result": sha(result) if result.exists() else None},
    }
    with (folder / "receipt.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "n": n, "case": kind,
                      "producer": receipt["producer_status"],
                      "parent_wall_seconds": wall / 1e9,
                      "sampled_peak_rss_bytes": peak}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int, choices=(41, 131))
    parser.add_argument("case", choices=("positive", "trace_zero_control"))
    args = parser.parse_args()
    main(args.n, args.case)
