#!/usr/bin/env python3
"""Run one frozen Q1420 projective-S3 CryptoMiniSat m6 attempt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

import build_projective as circuit


ref = circuit.ref
HERE = circuit.HERE


EXPECTED_SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"


def process_rss_bytes(pid):
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("RSS sampler unavailable: " + result.stderr.strip())
    value = result.stdout.strip()
    return int(value) * 1024 if value else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.POLICIES, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    stdout_path = args.out.with_suffix(".stdout.txt")
    stderr_path = args.out.with_suffix(".stderr.txt")
    if any(path.exists() for path in (args.out, stdout_path, stderr_path)):
        parser.error("refusing to overwrite pilot evidence")
    config = ref.read(HERE / "CONFIG.json")
    audit = ref.read(HERE / "runs/R1/build_audit.json")
    receipt_path = args.formula.with_suffix(".json")
    receipt = ref.read(receipt_path)
    if (audit["status"] != "PASS_TWO_GUARDED_PROJECTIVE_XCNFS"
            or audit["source_sha256"] != ref.sha(HERE / "audit_build.py")
            or receipt["schema"] != "ecc2k130-263-projective-s3-xcnf-v1"
            or receipt["policy"] != args.policy
            or receipt["projective_intermediates"] != 4
            or receipt["primary_workload_id"] != config["primary_workload_id"]
            or receipt["formula_sha256"] != ref.sha(args.formula)
            or audit["policies"][args.policy]["formula_sha256"]
            != receipt["formula_sha256"]
            or receipt["builder_sha256"] != ref.sha(HERE / "build_projective.py")
            or receipt["target_x_choices"] != [
                str(value) for value in circuit.finite.target_lifts(args.policy)]):
        raise ValueError("formula does not match independently replayed Q1420 input")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed from frozen kernel")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    limits = config["solver_pilot"]
    if (limits["attempts_per_policy"] != 1 or limits["threads"] != 1
            or limits["cryptominisat_maxtime_seconds"] != 120
            or limits["external_wall_limit_seconds"] != 150
            or limits["peak_rss_limit_bytes"] != 4 * (1 << 30)):
        raise ValueError("frozen pilot limits changed")
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler returned no data on preflight")
    command = [str(solver), "--threads=1", "--maxtime=120", "--verb=1",
               "--printsol=1", str(args.formula)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    peak_observed = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                elapsed = time.perf_counter()-started
                rss = process_rss_bytes(process.pid)
                peak_observed = max(peak_observed, rss)
                if rss > limits["peak_rss_limit_bytes"]:
                    guard = "RSS_CAP"
                if elapsed > limits["external_wall_limit_seconds"]:
                    guard = "WALL_CAP"
                if guard:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.25)
            exit_code = process.wait()
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    wall = time.perf_counter()-started
    peak_child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        peak_child *= 1024
    output = stdout_path.read_text(errors="replace")
    errors = stderr_path.read_text(errors="replace")
    sat = "s SATISFIABLE" in output
    unsat = "s UNSATISFIABLE" in output
    if guard == "RSS_CAP":
        status = "OOM_GUARD"
    elif guard == "WALL_CAP":
        status = "BOUNDED_UNKNOWN"
    elif sat and not unsat:
        status = "SAT_UNVERIFIED"
    elif unsat and not sat:
        status = "UNSAT"
    elif ("s INDETERMINATE" in output or "s UNKNOWN" in output
          or exit_code == 0 and "conflicts" in output.lower()):
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    progress = [line for line in output.splitlines()
                if "conflict" in line.lower() or "restarts" in line.lower()
                or line.startswith("s ")]
    result = {
        "schema": "ecc2k130-263-projective-s3-pilot-v1",
        "status": status,
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "policy": args.policy,
        "primary_workload_id": config["primary_workload_id"],
        "ordinary_query_index": config["query_index"],
        "target_lifts": 4,
        "formula_sha256": ref.sha(args.formula),
        "formula_receipt_sha256": ref.sha(receipt_path),
        "build_audit_sha256": ref.sha(HERE / "runs/R1/build_audit.json"),
        "solver_binary": str(solver),
        "solver_sha256": ref.sha(solver),
        "solver_version": version,
        "command": command,
        "threads": limits["threads"],
        "solver_maxtime_seconds": limits["cryptominisat_maxtime_seconds"],
        "external_wall_cap_seconds": limits["external_wall_limit_seconds"],
        "rss_cap_bytes": limits["peak_rss_limit_bytes"],
        "wall_seconds": wall,
        "peak_observed_rss_bytes": peak_observed,
        "peak_child_rss_bytes": peak_child,
        "guard": guard,
        "exit_code": exit_code,
        "stdout_sha256": ref.sha(stdout_path),
        "stderr_sha256": ref.sha(stderr_path),
        "search_progress_lines": len(progress),
        "search_evidence_tail": progress[-12:],
        "stdout_tail": output[-3000:],
        "stderr_tail": errors[-1000:],
        "verified_relation": False,
        "novel_rank": None,
        "runner_sha256": ref.sha(Path(__file__)),
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: result[key] for key in
                      ("policy", "status", "wall_seconds", "guard",
                       "exit_code", "peak_observed_rss_bytes",
                       "search_progress_lines")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
