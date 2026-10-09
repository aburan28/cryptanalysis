#!/usr/bin/env python3
"""Run frozen paired N41 public-target baseline and exact lookup queries."""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(value):
    temporary = RESULT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RESULT)


def preflight(protocol):
    if (protocol["status"] != "FROZEN" or
            protocol["target_count"] != 1 or protocol["batch"] is not False or
            protocol["run_order"] != ["baseline", "lookup"]):
        raise ValueError("invalid paired one-target protocol")
    checks = {"runtime": HERE / "runtime_info.json",
              "freeze": HERE / "freeze.py",
              "source": HERE / "source.xcnf",
              "source_pinned": HERE / "source_pinned.xcnf",
              "lookup": HERE / "lookup.xcnf",
              "table": HERE / "table.json",
              "solver": Path(protocol["solver"])}
    for key, path in checks.items():
        if sha(path) != protocol["source_sha256"][key]:
            raise ValueError(f"frozen source changed: {key}")
    ready = json.loads((HERE / "preflight.json").read_text())
    planted = json.loads((HERE / "planted_control.json").read_text())
    if (ready["status"] != "PASS_EXACT_GROUP_AND_XCNF" or
            ready["source_sha256"]["protocol"] != sha(HERE / "protocol.json") or
            planted["status"] != "PASS_FULL_PLANTED_XCNF_AND_LOOKUP_ROOT" or
            planted["source_sha256"]["protocol"] != sha(HERE / "protocol.json")):
        raise ValueError("independent preflight or planted control incomplete")


def attempt(arm, protocol):
    formula = HERE / ("source_pinned.xcnf" if arm == "baseline" else "lookup.xcnf")
    stdout_path = HERE / f"{arm}.stdout.txt"
    stderr_path = HERE / f"{arm}.stderr.txt"
    process_path = HERE / f"{arm}.process.json"
    if any(path.exists() for path in (stdout_path, stderr_path, process_path)):
        raise FileExistsError(f"{arm} already started")
    limit = protocol["per_arm_wall_cap_seconds"]
    command = [protocol["solver"], *protocol["solver_flags"],
               f"--maxtime={limit - 2}", str(formula)]
    began = time.monotonic()
    peak_rss = peak_cpu = 0
    stop_reason = None
    parent = psutil.Process(os.getpid())
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        child = psutil.Process(process.pid)
        process_path.write_text(json.dumps({
            "pid": process.pid, "create_time_epoch": child.create_time(),
            "command": command, "started_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2, sort_keys=True) + "\n")
        while process.poll() is None:
            try:
                cpu = child.cpu_times()
                peak_cpu = max(peak_cpu, cpu.user + cpu.system)
                peak_rss = max(peak_rss,
                               child.memory_info().rss + parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > protocol["combined_rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
                process.terminate()
                break
            if time.monotonic() - began >= limit:
                stop_reason = "WALL_CAP"
                process.terminate()
                break
            time.sleep(.1)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic() - began
    statuses = []
    model_lines = 0
    with stdout_path.open("rb") as stream:
        for line in stream:
            if line.startswith(b"s "):
                statuses.append(line.decode("ascii", "replace").strip())
            elif line.startswith(b"v "):
                model_lines += 1
    if "s SATISFIABLE" in statuses:
        status = "SAT_MODEL_PENDING_REPLAY" if model_lines else "SOLVER_MODEL_MISSING"
    elif "s UNSATISFIABLE" in statuses:
        status = "UNSAT_FORMULA"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    return {"arm": arm, "status": status,
            "exit_code": process.returncode, "stop_reason": stop_reason,
            "wall_seconds": wall, "sampled_peak_cpu_seconds": peak_cpu,
            "sampled_peak_combined_rss_bytes": peak_rss,
            "solver_status_lines": statuses, "model_lines": model_lines,
            "command": command,
            "source_sha256": {"formula": sha(formula), "stdout": sha(stdout_path),
                              "stderr": sha(stderr_path),
                              "process": sha(process_path)}}


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    preflight(protocol)
    if RESULT.exists():
        raise FileExistsError(RESULT)
    result = {"kind": "n41_phi_second_link_paired_public_target_query",
              "status": "RUNNING", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "run_id": None,
              "target_count": 1, "batch": False,
              "attempts": [], "verified_relations": 0,
              "complete_online_wall_seconds": None,
              "source_sha256": {"protocol": sha(protocol_path),
                                "preflight": sha(HERE / "preflight.json"),
                                "planted_control": sha(HERE / "planted_control.json"),
                                "runner": sha(Path(__file__))}}
    save(result)
    for arm in protocol["run_order"]:
        row = attempt(arm, protocol)
        result["attempts"].append(row)
        save(result)
        print(json.dumps({"arm": arm, "status": row["status"],
                          "wall_seconds": row["wall_seconds"]}), flush=True)
    result["solver_stage_wall_seconds"] = sum(row["wall_seconds"]
                                              for row in result["attempts"])
    result["status"] = "TERMINAL_PENDING_INDEPENDENT_AUDIT"
    save(result)


if __name__ == "__main__":
    main()
