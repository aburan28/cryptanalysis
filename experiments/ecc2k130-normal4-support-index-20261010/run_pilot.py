#!/usr/bin/env python3
"""Run one guarded native-XOR ordinary query for an exact selector policy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

import build_selector as circuit


PARENT_RUNNER = circuit.gate.PARENT / "run_pilot.py"
_spec = importlib.util.spec_from_file_location("_normal4_leaf_guard", PARENT_RUNNER)
if _spec is None or _spec.loader is None:
    raise ImportError("cannot load frozen parent RSS guard")
parent_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parent_guard)


MAX_WALL_SECONDS = 150
MAX_RSS_BYTES = 4 * (1 << 30)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.POLICIES, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    stdout_path = args.out.with_suffix(".stdout.txt")
    stderr_path = args.out.with_suffix(".stderr.txt")
    if any(path.exists() for path in (args.out, stdout_path, stderr_path)):
        parser.error("refusing to overwrite solver receipt or transcript")
    formula_receipt_path = args.formula.with_suffix(".json")
    built = json.loads(formula_receipt_path.read_text())
    if (built["schema"] != "ecc2k130-normal4-selector-xcnf-v1"
            or built["mode"] != "m6" or built["policy"] != args.policy
            or built["ordinary_query_index"] != 0
            or built["formula_sha256"] != circuit.ref.sha(args.formula)
            or built["builder_sha256"] != circuit.ref.sha(circuit.HERE / "build_selector.py")
            or built["target_x_choices"] != [
                str(value) for value in circuit.gate.target_lifts()]):
        raise ValueError("formula is not the frozen normal4 ordinary query")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if circuit.ref.sha(solver) != parent_guard.EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    command = [str(solver), "--threads=1", "--maxtime=120", "--verb=1",
               "--printsol=1", str(args.formula)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    peak_observed = 0
    guard = None
    producer_error = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                rss = parent_guard.process_rss_bytes(process.pid)
                if rss is not None:
                    peak_observed = max(peak_observed, rss)
                    if rss > MAX_RSS_BYTES:
                        guard = "RSS_CAP"
                if time.perf_counter() - started > MAX_WALL_SECONDS:
                    guard = "WALL_CAP"
                if guard:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.25)
            exit_code = process.wait()
        except Exception as error:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            exit_code = process.wait()
            producer_error = type(error).__name__ + ": " + str(error)
    wall = time.perf_counter() - started
    child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    child_rss *= 1 if sys.platform == "darwin" else 1024
    output = stdout_path.read_text(errors="replace")
    errors = stderr_path.read_text(errors="replace")
    sat = "s SATISFIABLE" in output
    unsat = "s UNSATISFIABLE" in output
    if producer_error is not None:
        status = "PRODUCER_FAILURE"
    elif guard == "RSS_CAP":
        status = "OOM_GUARD"
    elif guard == "WALL_CAP":
        status = "BOUNDED_UNKNOWN"
    elif sat and not unsat:
        status = "SAT_UNVERIFIED"
    elif unsat and not sat:
        status = "UNSAT"
    elif "s INDETERMINATE" in output or "s UNKNOWN" in output:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    restart_rows = [line for line in output.splitlines()
                    if line.lstrip().startswith("c rst")]
    receipt = {
        "schema": "ecc2k130-normal4-selector-pilot-v1",
        "status": status,
        "candidate_id": None,
        "policy": args.policy,
        "ordinary_query_index": 0,
        "target_lifts": 4,
        "formula_sha256": circuit.ref.sha(args.formula),
        "formula_receipt_sha256": circuit.ref.sha(formula_receipt_path),
        "solver_binary": str(solver),
        "solver_sha256": circuit.ref.sha(solver),
        "solver_version": version,
        "command": command,
        "threads": 1,
        "solver_maxtime_seconds": 120,
        "external_wall_cap_seconds": MAX_WALL_SECONDS,
        "rss_cap_bytes": MAX_RSS_BYTES,
        "wall_seconds": wall,
        "peak_observed_rss_bytes": peak_observed,
        "peak_child_rss_bytes": child_rss,
        "guard": guard,
        "producer_error": producer_error,
        "exit_code": exit_code,
        "stdout_sha256": circuit.ref.sha(stdout_path),
        "stderr_sha256": circuit.ref.sha(stderr_path),
        "live_restart_rows": len(restart_rows),
        "last_live_restart_row": restart_rows[-1] if restart_rows else None,
        "stdout_tail": output[-4000:],
        "stderr_tail": errors[-2000:],
        "verified_relation": False,
        "novel_rank": None,
        "runner_sha256": circuit.ref.sha(Path(__file__)),
        "parent_guard_sha256": circuit.ref.sha(
            circuit.gate.PARENT / "run_pilot.py"),
    }
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("policy", "status", "wall_seconds", "guard",
                       "exit_code", "peak_observed_rss_bytes",
                       "live_restart_rows")}, sort_keys=True))


if __name__ == "__main__":
    main()
