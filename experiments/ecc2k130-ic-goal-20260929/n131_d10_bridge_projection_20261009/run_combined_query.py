#!/usr/bin/env python3
"""Bounded N131 d10 precomputation query after CNF bridges and XOR projection."""

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
PROJECTION_DIR = HERE / "budget1"
FORMULA = PROJECTION_DIR / "projected.xcnf"
PROJECTION = PROJECTION_DIR / "result.json"
CERTIFICATE = PROJECTION_DIR / "independent_elimination_audit.json"
BRIDGE = HERE.parent / "n131_d10_xor_bridge_20261009/bridge_cnf/bridge_cnf.xcnf"
BRIDGE_AUDIT = HERE.parent / "n131_d10_xor_bridge_20261009/bridge_cnf/independent_audit.json"
GEOMETRY = HERE / "independent_component_geometry.json"
RAW = (HERE.parent /
            "n131_phi_torsion_frobenius_domains_20261005/m15_d10_static/"
            "single_target_runs/"
            "IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h91f3d222e01b"
            "W3c1992b7c92fR1/precomputation/target_0001/model_01/query.xcnf")
PROTOCOL = HERE / "protocol.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUN = HERE / "ordinary_precompute_R1"
RUNTIME = HERE / "sage_runtime_info.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_PROPOSAL"
    assert protocol["target_count"] == 1 and protocol["batch"] is False
    assert protocol["resource_limit_seconds"] == 580
    assert protocol["rss_limit_bytes"] == 4 * 1024**3
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    projection = json.loads(PROJECTION.read_text())
    assert projection["status"] == "PASS"
    assert json.loads(CERTIFICATE.read_text())["status"] == "PASS"
    assert json.loads(BRIDGE_AUDIT.read_text())[
        "status"] == "PASS_EQUIVALENT_AND_COMPONENT_FIT"
    assert json.loads(GEOMETRY.read_text())["status"] == "PASS_COMPONENT_FIT"
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    for key, path in (("formula", FORMULA), ("projection", PROJECTION),
                      ("bridge", BRIDGE), ("bridge_audit", BRIDGE_AUDIT),
                      ("geometry", GEOMETRY), ("raw", RAW),
                      ("elimination_audit", CERTIFICATE),
                      ("runtime", RUNTIME), ("solver", SOLVER),
                      ("runner", Path(__file__))):
        assert sha(path) == protocol["source_sha256"][key]
    assert projection["source_sha256"]["input_xcnf"] == sha(BRIDGE)
    assert projection["source_sha256"]["projected_xcnf"] == sha(FORMULA)
    assert not RUN.exists()
    flags = protocol["run_policy"]["solver_flags"]
    assert flags == ["--threads=1", "--verb=1", "--verbstat=2",
                     "--printsol=1", "--restartprint=10000000",
                     "--random=2026100618", "--maxtime=578.000",
                     "--maxmatrixrows=10000", "--maxmatrixcols=15000",
                     "--maxnummatrices=10", "--maxconfl=1000000000000"]
    command = [str(SOLVER), *flags, str(FORMULA)]
    if args.preflight_only:
        print(json.dumps({"status": "READY", "solver_launched": False,
                          "formula_sha256": sha(FORMULA)}))
        return
    RUN.mkdir()
    (RUN / "sage_runtime_info.json").write_bytes(RUNTIME.read_bytes())
    save(RUN / "started.json", {
        "status": "RUNNING", "started_utc": now(),
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "target_count": 1, "batch": False,
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(RUNTIME),
        "solver_command": command,
    })
    stdout_path = RUN / "cryptominisat.stdout.txt"
    stderr_path = RUN / "cryptominisat.stderr.txt"
    began = time.monotonic()
    peak_rss = 0
    stop_reason = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        save(RUN / "solver_process.json", {
            "pid": process.pid,
            "create_time_epoch": psutil.Process(process.pid).create_time(),
            "command": command,
        })
        while process.poll() is None:
            try:
                child_rss = psutil.Process(process.pid).memory_info().rss
            except psutil.NoSuchProcess:
                child_rss = 0
            peak_rss = max(peak_rss, child_rss +
                           psutil.Process(os.getpid()).memory_info().rss)
            if peak_rss > protocol["rss_limit_bytes"]:
                stop_reason = "RSS_CAP"
                process.terminate()
                break
            if time.monotonic() - began >= protocol["resource_limit_seconds"]:
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
        stop_reason = stop_reason or "SOLVER_TIME_LIMIT"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT"
    else:
        status = "INDETERMINATE"
    result = {
        "kind": "n131_d10_cnf_bridge_then_xor_projection_precompute_query_sat_stage",
        "status": status, "finished_utc": now(),
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "target_count": 1, "batch": False,
        "solver_wall_seconds": time.monotonic() - began,
        "solver_exit_code": process.returncode,
        "stop_reason": stop_reason,
        "combined_peak_rss_bytes": peak_rss,
        "solver_status_lines": statuses,
        "solver_model_line_count": model_lines,
        "verified_relation": None,
        "source_sha256": {
            "protocol": sha(PROTOCOL), "formula": sha(FORMULA),
            "runtime": sha(RUNTIME), "stdout": sha(stdout_path),
            "stderr": sha(stderr_path), "runner": sha(Path(__file__)),
            "solver": sha(SOLVER),
        },
    }
    save(RUN / "result.json", result)
    print(json.dumps({"status": status,
                      "solver_wall_seconds": result["solver_wall_seconds"],
                      "combined_peak_rss_bytes": peak_rss,
                      "solver_model_line_count": model_lines}))


if __name__ == "__main__":
    main()
