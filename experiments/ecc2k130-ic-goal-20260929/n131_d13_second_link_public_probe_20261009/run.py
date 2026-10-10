#!/usr/bin/env python3
"""Bound both lookup-guided first-link branches for one N131 public point."""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOOKUP = ROOT / "n131_d13_second_link_lookup_20261009"
FIRST = ROOT / "n131_d13_first_link_branches_20261009"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RAW = ROOT / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/official_q_phi_fiber_d13_m12_v1.xcnf"
RESULT = HERE / "result.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_result(record):
    temp = RESULT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(temp, RESULT)


def validate(protocol):
    if (protocol["status"] != "FROZEN_BEFORE_RUN" or
            protocol["target_count"] != 1 or protocol["workers"] != 1 or
            len(protocol["branches"]) != 2 or
            protocol["combined_solver_stage_cap_seconds"] > 600):
        raise ValueError("invalid one-point resource protocol")
    files = {"runner": HERE / "run.py", "freeze": HERE / "freeze.py",
             "source_protocol": FIRST / "protocol.json",
             "lookup_protocol": LOOKUP / "protocol.json",
             "encoding_audit": LOOKUP / "encoding_audit.json",
             "table_audit": LOOKUP / "audit.json",
             "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}
    for name, path in files.items():
        if sha(path) != protocol["source_sha256"][name]:
            raise ValueError(f"frozen source mismatch: {name}")
    if json.loads(files["runtime"].read_text())["status"] != "verified":
        raise ValueError("checked Sage runtime is unverified")
    if sha(RAW) != protocol["source_sha256"]["original_xcnf"]:
        raise ValueError("original public-point XCNF changed")
    for index, row in enumerate(protocol["branches"]):
        if row["branch"] != index or sha(LOOKUP / f"branch{index}_lookup.xcnf") != row["formula_sha256"]:
            raise ValueError(f"lookup formula mismatch: branch {index}")
    source = json.loads(files["source_protocol"].read_text())
    exact = json.loads(files["lookup_protocol"].read_text())
    if (len({protocol["curve_id"], source["curve_id"], exact["curve_id"]}) != 1 or
            len({protocol["workload_id"], source["workload_id"], exact["workload_id"]}) != 1):
        raise ValueError("curve/workload mismatch")


def attempt(index, protocol):
    stdout_path = HERE / f"branch{index}.stdout.txt"
    stderr_path = HERE / f"branch{index}.stderr.txt"
    process_path = HERE / f"branch{index}.process.json"
    if any(path.exists() for path in (stdout_path, stderr_path, process_path)):
        raise FileExistsError(f"branch {index} has already started")
    formula = LOOKUP / f"branch{index}_lookup.xcnf"
    limit = protocol["per_branch_parent_wall_cap_seconds"]
    command = [str(SOLVER), *protocol["solver_flags"],
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
                usage = child.cpu_times()
                peak_cpu = max(peak_cpu, usage.user + usage.system)
                peak_rss = max(peak_rss, child.memory_info().rss + parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > protocol["combined_process_rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
                process.terminate()
                break
            if time.monotonic() - began >= limit:
                stop_reason = "WALL_CAP"
                process.terminate()
                break
            time.sleep(0.1)
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
    if any(line == "s SATISFIABLE" for line in statuses):
        status = "SAT_MODEL_PENDING_INDEPENDENT_REPLAY" if model_lines else "SOLVER_MODEL_MISSING"
    elif any(line == "s UNSATISFIABLE" for line in statuses):
        status = "UNSAT_BRANCH"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "WALL_CAP" or any("INDETERMINATE" in line for line in statuses):
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    return {"branch": index, "status": status, "exit_code": process.returncode,
            "stop_reason": stop_reason, "solver_status_lines": statuses,
            "model_lines": model_lines, "wall_seconds": wall,
            "sampled_cpu_seconds": peak_cpu,
            "sampled_peak_combined_rss_bytes": peak_rss, "command": command,
            "source_sha256": {"formula": sha(formula), "stdout": sha(stdout_path),
                              "stderr": sha(stderr_path), "process": sha(process_path)}}


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    validate(protocol)
    if RESULT.exists():
        raise FileExistsError(RESULT)
    record = {"kind": protocol["kind"], "status": "RUNNING",
              "proposal_id": protocol["proposal_id"], "candidate_id": None,
              "run_id": None, "curve_id": protocol["curve_id"],
              "workload_id": protocol["workload_id"], "target_count": 1,
              "verified_relations": 0, "useful_rank": 0,
              "complete_online_wall_seconds": None, "attempts": [],
              "source_sha256": {"protocol": sha(protocol_path), "runner": sha(Path(__file__))}}
    write_result(record)
    for index in range(2):
        row = attempt(index, protocol)
        record["attempts"].append(row)
        write_result(record)
        print(json.dumps({"branch": index, "status": row["status"],
                          "wall_seconds": row["wall_seconds"]}), flush=True)
        if row["status"] == "SAT_MODEL_PENDING_INDEPENDENT_REPLAY":
            break
    record["solver_stage_wall_seconds"] = sum(x["wall_seconds"] for x in record["attempts"])
    record["status"] = ("SAT_MODEL_PENDING_INDEPENDENT_REPLAY" if any(
        x["status"] == "SAT_MODEL_PENDING_INDEPENDENT_REPLAY" for x in record["attempts"])
        else "CENSORED_OR_NO_MODEL")
    write_result(record)


if __name__ == "__main__":
    main()
