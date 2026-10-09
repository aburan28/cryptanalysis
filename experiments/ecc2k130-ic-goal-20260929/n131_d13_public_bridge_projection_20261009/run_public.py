#!/usr/bin/env python3
"""Run an audited N131 d13 public-Q formula with XOR rediscovery disabled."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = HERE
FORMULA = SOURCE / "budget1/projected.xcnf"
BRIDGE = HERE / "bridge_cnf/bridge_cnf.xcnf"
RAW = (PARENT / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/"
       "official_q_phi_fiber_d13_m12_v1.xcnf")
PREVIOUS = (PARENT / "n131_d13_projected_public_q_20261009/"
            "public_q_stage_run_R2/cryptominisat.stdout.txt")
D10_CONTROL = PARENT / "n131_d10_no_xor_discovery_20261009/full"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "sage_runtime_info.json"
PROTOCOL = HERE / "solver_protocol.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def preceding_control_drained():
    process_path = D10_CONTROL / "solver_process.json"
    result_path = D10_CONTROL / "result.json"
    if not process_path.exists() or not result_path.exists():
        return False
    process = json.loads(process_path.read_text())
    result = json.loads(result_path.read_text())
    if result.get("status") not in ("CENSORED_TIME", "OOM", "UNSAT",
                                     "INDETERMINATE", "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT"):
        return False
    try:
        live = psutil.Process(process["pid"])
    except psutil.NoSuchProcess:
        return True
    return not (abs(live.create_time() - process["create_time_epoch"]) < .05 and
                live.is_running() and live.status() != psutil.STATUS_ZOMBIE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_PROPOSAL"
    assert protocol["target_count"] == 1 and protocol["batch"] is False
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    paths = {
        "formula": FORMULA, "bridge": BRIDGE, "raw": RAW,
        "solver": SOLVER, "runtime": RUNTIME, "runner": Path(__file__),
        "bridge_audit": HERE / "bridge_cnf/independent_audit.json",
        "projection_audit": SOURCE / "budget1/independent_elimination_audit.json",
        "component_audit": SOURCE / "component_audit.json",
        "old_solver_log": PREVIOUS,
    }
    for name, path in paths.items():
        assert sha(path) == protocol["source_sha256"][name], (name, path)
    assert json.loads(paths["bridge_audit"].read_text())["status"] == "PASS_EQUIVALENT_AND_COMPONENT_FIT"
    assert json.loads(paths["projection_audit"].read_text())["status"] == "PASS"
    assert json.loads(paths["component_audit"].read_text())["status"] == "PASS_COMPONENT_FIT"
    run = HERE / "public_q_stage_R1"
    assert not run.exists()
    limit = protocol["limit"]["full_wall_seconds"]
    flags = protocol["solver_flags_common"]
    assert "--xor=0" in flags and "--maxnummatrices=10" in flags
    command = [str(SOLVER), *flags, "--maxtime=%d" % (limit - 2), str(FORMULA)]
    drain_ready = preceding_control_drained()
    if args.check_only:
        print(json.dumps({"status": "READY" if drain_ready else "WAIT_FOR_D10_CONTROL_DRAIN",
                          "query_role": protocol["query_role"],
                          "formula_sha256": sha(FORMULA), "solver_command": command}))
        return
    if not drain_ready:
        raise RuntimeError("preceding d10 control is not terminal and drained")
    run.mkdir()
    (run / "sage_runtime_info.json").write_bytes(RUNTIME.read_bytes())
    save(run / "started.json", {
        "status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "batch": False,
        "protocol_sha256": sha(PROTOCOL), "runtime_info_sha256": sha(RUNTIME),
        "solver_command": command,
    })
    stdout_path = run / "cryptominisat.stdout.txt"
    stderr_path = run / "cryptominisat.stderr.txt"
    began = time.monotonic()
    peak_rss = 0
    peak_cpu_seconds = 0.0
    stop_reason = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        child = psutil.Process(process.pid)
        save(run / "solver_process.json", {
            "pid": process.pid, "create_time_epoch": child.create_time(),
            "command": command,
        })
        while process.poll() is None:
            try:
                child_rss = child.memory_info().rss
                cpu = child.cpu_times()
                peak_cpu_seconds = max(peak_cpu_seconds, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                child_rss = 0
            peak_rss = max(peak_rss, child_rss + psutil.Process(os.getpid()).memory_info().rss)
            if peak_rss > protocol["limit"]["combined_rss_bytes"]:
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
    statuses = []
    model_lines = 0
    for line in stdout_path.open("rb"):
        if line.startswith(b"s "):
            statuses.append(line.decode("ascii", errors="replace").strip())
        elif line.startswith(b"v "):
            model_lines += 1
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "WALL_CAP" or statuses == ["s INDETERMINATE"]:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT"
    else:
        status = "INDETERMINATE"
    save(run / "result.json", {
        "kind": "n131_d13_public_q_exact_bridge_projected_solver_stage",
        "status": status,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "batch": False,
        "solver_wall_seconds": time.monotonic() - began,
        "solver_cpu_seconds_lower_bound": peak_cpu_seconds,
        "solver_exit_code": process.returncode,
        "stop_reason": stop_reason,
        "combined_peak_rss_bytes": peak_rss,
        "solver_status_lines": statuses,
        "solver_model_line_count": model_lines,
        "verified_relation": None,
        "source_sha256": {"protocol": sha(PROTOCOL), "formula": sha(FORMULA),
                          "runtime": sha(RUNTIME), "stdout": sha(stdout_path),
                          "stderr": sha(stderr_path), "runner": sha(Path(__file__)),
                          "solver": sha(SOLVER)},
    })
    print(json.dumps({"status": status,
                      "solver_wall_seconds": time.monotonic() - began,
                      "combined_peak_rss_bytes": peak_rss,
                      "solver_model_line_count": model_lines}))


if __name__ == "__main__":
    main()
