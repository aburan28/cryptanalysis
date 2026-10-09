#!/usr/bin/env python3
"""Run both exact first-link branches for one supplied N131 public point."""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RESULT = HERE / "result.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(record):
    temp = RESULT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(temp, RESULT)


def validate(protocol):
    if (protocol["status"] != "FROZEN_PROPOSAL" or
            protocol["target_count"] != 1 or protocol["batch"] is not False or
            len(protocol["cubes"]) != 2):
        raise ValueError("invalid one-public-target protocol")
    checks = {
        "solver": SOLVER,
        "freeze": HERE / "freeze.py",
        "runtime": HERE / "runtime_info.json",
        "prior_cube0": HERE.parent / "n131_d13_two_leaf_cubes_20261009/cube0.xcnf",
        "roots": HERE.parent / "n131_d13_two_leaf_cubes_20261009/first_link_candidates.json",
        "raw": (HERE.parent / "n131_phi_torsion_frobenius_domains_20261005/"
                "d13_m12_probe/official_q_phi_fiber_d13_m12_v1.xcnf"),
        "projected": HERE.parent / "n131_d13_public_bridge_projection_20261009/"
                     "budget1/projected.xcnf",
        "mapping": HERE.parent / "n131_d13_public_bridge_projection_20261009/"
                   "budget1/variable_map.json",
    }
    for key, path in checks.items():
        if sha(path) != protocol["source_sha256"][key]:
            raise ValueError(f"frozen source mismatch: {key}")
    if json.loads(checks["runtime"].read_text())["status"] != "verified":
        raise ValueError("checked Sage runtime is unverified")
    for index, cube in enumerate(protocol["cubes"]):
        if sha(HERE / f"branch{index}.xcnf") != cube["formula_sha256"]:
            raise ValueError(f"branch {index} formula changed")


def attempt(index, protocol):
    stdout_path = HERE / f"branch{index}.stdout.txt"
    stderr_path = HERE / f"branch{index}.stderr.txt"
    process_path = HERE / f"branch{index}.process.json"
    if any(path.exists() for path in (stdout_path, stderr_path, process_path)):
        raise FileExistsError(f"branch {index} already started")
    formula = HERE / f"branch{index}.xcnf"
    limit = protocol["per_cube_wall_cap_seconds"]
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
                rss = child.memory_info().rss + parent.memory_info().rss
                peak_rss = max(peak_rss, rss)
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
    if any("SATISFIABLE" in line and "UNSAT" not in line for line in statuses):
        status = "SAT_MODEL_PENDING_INDEPENDENT_AUDIT" if model_lines else "SOLVER_MODEL_MISSING"
    elif any("UNSATISFIABLE" in line for line in statuses):
        status = "UNSAT_BRANCH"
    elif stop_reason == "WALL_CAP" or any("INDETERMINATE" in line for line in statuses):
        status = "CENSORED_TIME"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    return {
        "branch": index, "leaf_codes": protocol["cubes"][index]["leaf_codes"],
        "partial0_phi_mask": protocol["cubes"][index]["partial0_phi_mask"],
        "status": status, "exit_code": process.returncode, "stop_reason": stop_reason,
        "wall_seconds": wall, "sampled_peak_cpu_seconds": peak_cpu,
        "sampled_peak_combined_rss_bytes": peak_rss,
        "solver_status_lines": statuses, "model_lines": model_lines,
        "command": command, "source_sha256": {
            "formula": sha(formula), "stdout": sha(stdout_path),
            "stderr": sha(stderr_path), "process": sha(process_path),
        },
    }


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    validate(protocol)
    if RESULT.exists():
        raise FileExistsError(RESULT)
    record = {
        "kind": "n131_d13_m12_exact_first_link_root_branch_query",
        "status": "RUNNING", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "batch": False, "attempts": [],
        "verified_relations": 0, "useful_rank": 0,
        "complete_online_wall_seconds": None,
        "source_sha256": {"protocol": sha(protocol_path), "runner": sha(Path(__file__))},
    }
    save(record)
    for index in range(2):
        row = attempt(index, protocol)
        record["attempts"].append(row)
        save(record)
        print(json.dumps({"branch": index, "status": row["status"],
                          "wall_seconds": row["wall_seconds"]}), flush=True)
        if row["status"] == "SAT_MODEL_PENDING_INDEPENDENT_AUDIT":
            break
    record["solver_stage_wall_seconds"] = sum(row["wall_seconds"] for row in record["attempts"])
    record["status"] = ("SAT_MODEL_PENDING_INDEPENDENT_AUDIT" if any(
        row["status"] == "SAT_MODEL_PENDING_INDEPENDENT_AUDIT" for row in record["attempts"])
        else "CENSORED_OR_NO_MODEL")
    save(record)


if __name__ == "__main__":
    main()
