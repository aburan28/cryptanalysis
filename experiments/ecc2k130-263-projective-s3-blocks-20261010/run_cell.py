#!/usr/bin/env python3
"""Run one frozen block-isolation CryptoMiniSat cell with external guards."""

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

import common
from run_build import process_rss_bytes


ref = common.ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("source", "descendant_native"),
                        required=True)
    parser.add_argument("--mode", choices=("intermediate_free", "leaf_free"),
                        required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    config, _, _ = common.load_config()
    prefix = args.out_dir / (args.policy + "_" + args.mode)
    formula = prefix.with_suffix(".xcnf")
    stdout_path = prefix.with_suffix(".stdout.txt")
    stderr_path = prefix.with_suffix(".stderr.txt")
    receipt_path = prefix.with_suffix(".solver.json")
    if any(path.exists() for path in (stdout_path, stderr_path, receipt_path)):
        parser.error("refusing to overwrite solver evidence")
    cells_path = args.out_dir / (args.policy + "_cells.json")
    cells = ref.read(cells_path)
    cell = cells["cells"][args.mode]
    if (cells["schema"] != "ecc2k130-263-projective-s3-search-block-cells-v1"
            or cells["status"] != "PASS_EXACT_INPUT_PARTITION"
            or cells["policy"] != args.policy
            or cells["config_sha256"] != ref.sha(common.HERE / "CONFIG.json")
            or cells["common_source_sha256"] != ref.sha(
                common.HERE / "common.py")
            or cells["producer_sha256"] != ref.sha(common.HERE / "make_cells.py")
            or cell["xcnf_sha256"] != ref.sha(formula)
            or config["attempts_per_cell"] != 1
            or config["threads"] != 1
            or config["solver_maxtime_seconds"] != 120
            or config["solver_external_wall_cap_seconds"] != 150
            or config["solver_peak_rss_cap_bytes"] != 4 * (1 << 30)):
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
    command = [str(solver), "--threads=1", "--maxtime=120", "--verb=1",
               "--printsol=1", str(formula)]
    started = time.perf_counter()
    peak = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                wall = time.perf_counter() - started
                peak = max(peak, process_rss_bytes(process.pid))
                if peak > config["solver_peak_rss_cap_bytes"]:
                    guard = "RSS_CAP"
                if wall > config["solver_external_wall_cap_seconds"]:
                    guard = "WALL_CAP"
                if guard is not None:
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
        "schema": "ecc2k130-263-projective-s3-search-block-solver-v1",
        "status": status,
        "policy": args.policy,
        "mode": args.mode,
        "candidate_id": None,
        "formula_sha256": ref.sha(formula),
        "cell_receipt_sha256": ref.sha(cells_path),
        "solver_sha256": ref.sha(solver),
        "solver_version": version,
        "command": command,
        "threads": 1,
        "solver_maxtime_seconds": 120,
        "external_wall_cap_seconds": 150,
        "rss_cap_bytes": config["solver_peak_rss_cap_bytes"],
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
        "config_sha256": ref.sha(common.HERE / "CONFIG.json"),
        "common_source_sha256": ref.sha(common.HERE / "common.py"),
        "runner_sha256": ref.sha(Path(__file__)),
    }
    common.write_json(receipt_path, result)
    print(json.dumps({key: result[key] for key in
                      ("policy", "mode", "status", "wall_seconds", "exit_code",
                       "peak_observed_rss_bytes", "peak_child_rss_bytes")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
