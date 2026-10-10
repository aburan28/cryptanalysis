#!/usr/bin/env python3
"""Run one frozen exceptional-control CryptoMiniSat cell with resource guards."""

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

import build_control as circuit
from run_build import process_rss_bytes


HERE = Path(__file__).resolve().parent
ref = circuit.ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.parent.POLICIES, required=True)
    parser.add_argument("--mode", choices=("positive", "negative", "free"),
                        required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    prefix = args.out_dir / (args.policy + "_" + args.mode)
    formula = prefix.with_suffix(".xcnf")
    stdout_path = prefix.with_suffix(".stdout.txt")
    stderr_path = prefix.with_suffix(".stderr.txt")
    result_path = prefix.with_suffix(".solver.json")
    if any(path.exists() for path in (stdout_path, stderr_path, result_path)):
        parser.error("refusing to overwrite solver evidence")
    config = ref.read(HERE / "CONFIG.json")
    cells = ref.read(args.out_dir / (args.policy + "_cells.json"))
    cell = cells["cells"][args.mode]
    maxtime = (config["free_control_solver_maxtime_seconds"]
               if args.mode == "free" else
               config["fixed_control_solver_maxtime_seconds"])
    wall_cap = (config["free_control_external_wall_cap_seconds"]
                if args.mode == "free" else
                config["fixed_control_external_wall_cap_seconds"])
    rss_cap = config["solver_peak_rss_cap_bytes"]
    if (cells["status"] != "PASS_THREE_EXACT_SAT_INPUTS"
            or cells["policy"] != args.policy
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(HERE / "make_cells.py")
            or cell["xcnf_sha256"] != ref.sha(formula)
            or config["attempts_per_cell"] != 1
            or config["threads"] != 1 or rss_cap != 4 * (1 << 30)
            or (maxtime, wall_cap) not in ((45, 60), (120, 150))):
        raise ValueError("frozen SAT input or limits changed")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != config["solver_sha256"]:
        raise ValueError("frozen solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight returned no data")
    command = [str(solver), "--threads=1", f"--maxtime={maxtime}",
               "--verb=1", "--printsol=1", str(formula)]
    started = time.perf_counter()
    peak = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                rss = process_rss_bytes(process.pid)
                peak = max(peak, rss)
                if rss > rss_cap:
                    guard = "RSS_CAP"
                if elapsed > wall_cap:
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
    peak_child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        peak_child *= 1024
    output = stdout_path.read_text(errors="replace")
    terminal = [line.strip() for line in output.splitlines()
                if line.startswith("s ")]
    if guard == "RSS_CAP":
        status = "OOM_GUARD"
    elif guard == "WALL_CAP":
        status = "BOUNDED_UNKNOWN"
    elif terminal == ["s SATISFIABLE"] and exit_code == 10:
        status = "SAT_UNVERIFIED"
    elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
        status = "UNSAT"
    elif terminal == ["s INDETERMINATE"] and exit_code == 15:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    result = {
        "schema": "ecc2k130-263-projective-s3-sat-solver-v1",
        "status": status,
        "policy": args.policy,
        "mode": args.mode,
        "candidate_id": None,
        "formula_sha256": ref.sha(formula),
        "cell_receipt_sha256": ref.sha(
            args.out_dir / (args.policy + "_cells.json")),
        "solver_sha256": ref.sha(solver),
        "solver_version": version,
        "command": command,
        "threads": 1,
        "solver_maxtime_seconds": maxtime,
        "external_wall_cap_seconds": wall_cap,
        "rss_cap_bytes": rss_cap,
        "wall_seconds": wall,
        "peak_observed_rss_bytes": peak,
        "peak_child_rss_bytes": peak_child,
        "guard": guard,
        "exit_code": exit_code,
        "terminal_status_lines": terminal,
        "stdout_sha256": ref.sha(stdout_path),
        "stderr_sha256": ref.sha(stderr_path),
        "stdout_bytes": stdout_path.stat().st_size,
        "stderr_bytes": stderr_path.stat().st_size,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "runner_sha256": ref.sha(Path(__file__)),
    }
    result_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("policy", "mode", "status", "wall_seconds", "exit_code",
                       "peak_observed_rss_bytes")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
