#!/usr/bin/env python3
"""Run one frozen target-guided N41 public-target phi-chain query."""

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


def save(record):
    temporary = RESULT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RESULT)


def validate(protocol):
    if (protocol["status"] != "FROZEN" or protocol["target_count"] != 1 or
            protocol["batch"] is not False or
            protocol["wall_cap_seconds"] != 240):
        raise ValueError("invalid frozen one-target protocol")
    checks = {"runtime": HERE / "runtime_info.json",
              "builder": HERE / "build.py",
              "suffix": HERE / "suffix_masks.json",
              "guided": HERE / "guided.xcnf",
              "solver": Path(protocol["solver"]),
              "previous_lookup": (HERE.parent / "n41_phi_second_link_control_20261009/"
                                  "lookup.xcnf")}
    for key, path in checks.items():
        if sha(path) != protocol["source_sha256"][key]:
            raise ValueError(f"frozen source changed: {key}")
    ready = json.loads((HERE / "preflight.json").read_text())
    if (ready["status"] != "PASS_COMPLETE_SUFFIX_AND_XCNF" or
            ready["source_sha256"]["protocol"] != sha(HERE / "protocol.json") or
            ready["source_sha256"]["guided"] != sha(HERE / "guided.xcnf")):
        raise ValueError("independent suffix preflight changed")


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    validate(protocol)
    stdout_path, stderr_path = (HERE / name for name in
                                ("solver.stdout.txt", "solver.stderr.txt"))
    process_path = HERE / "solver.process.json"
    if any(path.exists() for path in (RESULT, stdout_path, stderr_path,
                                      process_path)):
        raise FileExistsError("preserve prior target-guided attempt")
    formula = HERE / "guided.xcnf"
    limit = protocol["wall_cap_seconds"]
    command = [protocol["solver"], *protocol["solver_flags"],
               f"--maxtime={limit - 2}", str(formula)]
    result = {
        "kind": "n41_phi_target_conditioned_suffix2_public_query",
        "status": "RUNNING", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "batch": False,
        "target_conditioned_build_seconds": protocol["target_conditioned_build_seconds"],
        "target_independent_pair_sum_seconds": protocol["reusable_pair_sum_seconds"],
        "verified_relations": 0, "complete_online_wall_seconds": None,
        "source_sha256": {"protocol": sha(protocol_path),
                          "preflight": sha(HERE / "preflight.json"),
                          "runner": sha(Path(__file__))},
    }
    save(result)
    started = time.monotonic()
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
            if time.monotonic() - started >= limit:
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
    wall = time.monotonic() - started
    statuses = []
    models = 0
    with stdout_path.open("rb") as stream:
        for line in stream:
            if line.startswith(b"s "):
                statuses.append(line.decode("ascii", "replace").strip())
            elif line.startswith(b"v "):
                models += 1
    if "s SATISFIABLE" in statuses:
        status = "SAT_MODEL_PENDING_REPLAY" if models else "SOLVER_MODEL_MISSING"
    elif "s UNSATISFIABLE" in statuses:
        status = "UNSAT_FORMULA"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result.update({
        "status": status, "exit_code": process.returncode,
        "stop_reason": stop_reason,
        "solver_stage_wall_seconds": wall,
        "sampled_peak_cpu_seconds": peak_cpu,
        "sampled_peak_combined_rss_bytes": peak_rss,
        "solver_status_lines": statuses, "model_lines": models,
        "command": command,
        "known_target_dependent_stage_seconds": (
            protocol["target_conditioned_build_seconds"] + wall),
        "source_sha256": {**result["source_sha256"],
                          "formula": sha(formula), "stdout": sha(stdout_path),
                          "stderr": sha(stderr_path),
                          "process": sha(process_path)},
    })
    save(result)
    print(json.dumps({"status": status, "solver_wall_seconds": wall,
                      "known_target_dependent_stage_seconds":
                      result["known_target_dependent_stage_seconds"]}))


if __name__ == "__main__":
    main()
