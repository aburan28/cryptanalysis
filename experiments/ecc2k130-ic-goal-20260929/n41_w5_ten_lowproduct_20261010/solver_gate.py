#!/usr/bin/env python3
"""Bounded unpinned SAT query for the pair-frame public N41 formula."""
import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from audit import GATE, HERE, JOIN, sha

FORMULA = HERE / "public_relation_frame.xcnf"
AUDIT = HERE / "frame_audit.json"
PROTOCOL = HERE / "solver_protocol.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=2000000", "--maxtime=112"]
CAP_SECONDS = 115
RSS_CAP_BYTES = 4 * 1024**3


def save(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__), "circuit": HERE / "circuit.py",
            "audit_script": HERE / "audit.py", "frame_audit": AUDIT,
            "formula": FORMULA, "geometry": GATE / "geometry_result.json",
            "public_relation": JOIN / "run/hits.jsonl", "solver": SOLVER}


def freeze():
    audit = json.loads(AUDIT.read_text())
    assert audit["status"] == "PASS_PUBLIC_RELATION_XCNF_ASSIGNMENT"
    assert audit["method"]["pair_local_frobenius_frames"]
    assert audit["formula"]["sha256"] == sha(FORMULA)
    protocol = {"status": "FROZEN_BEFORE_UNPINNED_SAT_QUERY",
                "candidate_id": None, "curve_id": audit["curve_id"],
                "target_count": 1, "public_target_q": audit["public_target_q"],
                "summands": 10,
                "actual_factor_base_points_B": audit["actual_factor_base_points_B"],
                "effective_folded_columns_K": audit["effective_folded_columns_K"],
                "input_law": "same frozen public point; masks, signs and intermediates unpinned",
                "scope": "SAT-stage diagnostic on prebuilt target formula",
                "solver_flags": FLAGS, "wall_cap_seconds": CAP_SECONDS,
                "rss_cap_bytes": RSS_CAP_BYTES,
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(PROTOCOL, protocol)
    print(json.dumps({"status": protocol["status"],
                      "formula_sha256": sha(FORMULA)}))


def query():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_UNPINNED_SAT_QUERY"
    assert protocol["source_sha256"] == {name: sha(path)
                                           for name, path in sources().items()}
    folder = HERE / "solver_run"
    folder.mkdir(exist_ok=False)
    command = [str(SOLVER), *FLAGS, str(FORMULA)]
    stdout_path = folder / "stdout.txt"
    stderr_path = folder / "stderr.txt"
    parent = psutil.Process(os.getpid())
    peak_rss = peak_cpu = 0
    stop_reason = None
    began = time.monotonic()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        child = psutil.Process(process.pid)
        save(folder / "process.json",
             {"pid": process.pid, "create_time_epoch": child.create_time(),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "command": command, "protocol_sha256": sha(PROTOCOL)})
        while process.poll() is None:
            try:
                cpu = child.cpu_times()
                peak_cpu = max(peak_cpu, cpu.user + cpu.system)
                peak_rss = max(peak_rss, child.memory_info().rss +
                               parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > RSS_CAP_BYTES:
                stop_reason = "RSS_CAP"
                process.terminate()
                break
            if time.monotonic() - began >= CAP_SECONDS:
                stop_reason = "WALL_CAP"
                process.terminate()
                break
            time.sleep(.1)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic() - began
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_PENDING_INDEPENDENT_REPLAY"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {"status": status, "solver_status_lines": statuses,
              "model_lines": model_lines, "exit_code": process.returncode,
              "stop_reason": stop_reason, "wall_seconds": wall,
              "sampled_peak_combined_rss_bytes": peak_rss,
              "sampled_solver_cpu_seconds": peak_cpu,
              "source_sha256": {"protocol": sha(PROTOCOL),
                                "stdout": sha(stdout_path),
                                "stderr": sha(stderr_path),
                                "process": sha(folder / "process.json")}}
    save(folder / "result.json", result)
    print(json.dumps({"status": status, "wall_seconds": wall,
                      "peak_rss_bytes": peak_rss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "query"))
    {"freeze": freeze, "query": query}[parser.parse_args().mode]()
