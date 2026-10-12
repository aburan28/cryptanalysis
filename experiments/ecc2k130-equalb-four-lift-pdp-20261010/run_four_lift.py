#!/usr/bin/env python3
"""Guard one exact all-lift m6 CryptoMiniSat ordinary-query attempt."""

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

import build_four_lift as gate
import run_pilot as parent_guard


MAX_WALL_SECONDS = 150
MAX_RSS_BYTES = 4 * (1 << 30)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=gate.POLICIES, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if (args.out.exists() or args.out.with_suffix(".stdout.txt").exists()
            or args.out.with_suffix(".stderr.txt").exists()):
        parser.error("refusing to overwrite solver receipt or transcript")
    formula_receipt_path = args.formula.with_suffix(".json")
    formula_receipt = json.loads(formula_receipt_path.read_text())
    if (formula_receipt["schema"] != "ecc2k130-equalb-four-lift-m6-xcnf-v1"
            or formula_receipt["policy"] != args.policy
            or formula_receipt["ordinary_query_index"] != 0
            or formula_receipt["formula_sha256"] != gate.ref.sha(args.formula)
            or formula_receipt["builder_sha256"] != gate.ref.sha(
                gate.HERE / "build_four_lift.py")
            or formula_receipt["target_x_choices"] != [
                str(x) for x in gate.target_lifts()]):
        raise ValueError("formula is not the frozen all-lift ordinary query")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if gate.ref.sha(solver) != parent_guard.EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed from parent gate")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    command = [str(solver), "--threads=1", "--maxtime=120", "--verb=1",
               "--printsol=1", str(args.formula)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = args.out.with_suffix(".stdout.txt")
    stderr_path = args.out.with_suffix(".stderr.txt")
    started = time.perf_counter()
    peak_observed = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                rss = parent_guard.process_rss_bytes(process.pid)
                if rss is not None:
                    peak_observed = max(peak_observed, rss)
                    if rss > MAX_RSS_BYTES:
                        guard = "RSS_CAP"
                if elapsed > MAX_WALL_SECONDS:
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
    wall = time.perf_counter() - started
    peak_children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_children *= 1 if sys.platform == "darwin" else 1024
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
          or exit_code == 0 and "c conflicts" in output.lower()):
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    progress = [line for line in output.splitlines()
                if ("conflict" in line.lower() or "restarts" in line.lower()
                    or line.startswith("s "))]
    receipt = {
        "schema": "ecc2k130-equalb-four-lift-m6-pilot-v1",
        "status": status,
        "candidate_id": None,
        "policy": args.policy,
        "ordinary_query_index": 0,
        "target_lifts": 4,
        "formula_sha256": gate.ref.sha(args.formula),
        "formula_receipt_sha256": gate.ref.sha(formula_receipt_path),
        "solver_binary": str(solver),
        "solver_sha256": gate.ref.sha(solver),
        "solver_version": version,
        "command": command,
        "threads": 1,
        "solver_maxtime_seconds": 120,
        "external_wall_cap_seconds": MAX_WALL_SECONDS,
        "rss_cap_bytes": MAX_RSS_BYTES,
        "wall_seconds": wall,
        "peak_observed_rss_bytes": peak_observed,
        "peak_child_rss_bytes": peak_children,
        "guard": guard,
        "exit_code": exit_code,
        "stdout_sha256": gate.ref.sha(stdout_path),
        "stderr_sha256": gate.ref.sha(stderr_path),
        "search_progress_lines": len(progress),
        "search_evidence_tail": progress[-12:],
        "stdout_tail": output[-4000:],
        "stderr_tail": errors[-2000:],
        "verified_relation": False,
        "novel_rank": None,
        "runner_sha256": gate.ref.sha(Path(__file__)),
        "parent_guard_sha256": gate.ref.sha(gate.PARENT / "run_pilot.py"),
    }
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("policy", "status", "wall_seconds", "guard",
                       "exit_code", "peak_observed_rss_bytes",
                       "search_progress_lines")}, sort_keys=True))


if __name__ == "__main__":
    main()
