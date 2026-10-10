#!/usr/bin/env python3
"""One bounded CryptoMiniSat attempt on a preregistered ordinary m6 query."""

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

import field as ref


HERE = Path(__file__).resolve().parent
EXPECTED_SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
MAX_WALL_SECONDS = 150
MAX_RSS_BYTES = 4 * (1 << 30)


def process_rss_bytes(pid: int) -> int | None:
    probe = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                           text=True, capture_output=True, check=False)
    value = probe.stdout.strip()
    return int(value) * 1024 if value.isdigit() else None


def solve(policy: str, formula: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError("refusing to overwrite a pilot receipt")
    if policy not in ("w24_source", "normal4_source"):
        raise ValueError("unfrozen source policy")
    formula_receipt = json.loads(formula.with_suffix(".json").read_text())
    if (formula_receipt["mode"] != "m6"
            or formula_receipt["policy"] != policy
            or formula_receipt["query_index"] != 0
            or formula_receipt["formula_sha256"] != ref.sha(formula)
            or formula_receipt["build_source_sha256"]
            != ref.sha(HERE / "build_formula.py")):
        raise ValueError("formula is not the preregistered ordinary q0 gate")
    binary_name = shutil.which("cryptominisat5")
    if binary_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    binary = Path(binary_name).resolve()
    if ref.sha(binary) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed from preregistration")
    version = subprocess.run([str(binary), "--version"],
                             text=True, capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")

    out.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = out.with_suffix(".stdout.txt")
    stderr_path = out.with_suffix(".stderr.txt")
    command = [str(binary), "--threads=1", "--maxtime=120", "--verb=1",
               "--printsol=1", str(formula)]
    started = time.perf_counter()
    peak_observed = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                rss = process_rss_bytes(process.pid)
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
    search_evidence = [line for line in output.splitlines()
                       if ("conflict" in line.lower()
                           or "restarts" in line.lower()
                           or line.startswith("s "))]
    receipt = {
        "schema": "ecc2k130-equalb-m6-ordinary-pilot-v1",
        "status": status,
        "candidate_id": None,
        "policy": policy,
        "ordinary_query_index": 0,
        "formula_sha256": ref.sha(formula),
        "formula_receipt_sha256": ref.sha(formula.with_suffix(".json")),
        "solver_binary": str(binary),
        "solver_sha256": ref.sha(binary),
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
        "stdout_sha256": ref.sha(stdout_path),
        "stderr_sha256": ref.sha(stderr_path),
        "search_evidence_tail": search_evidence[-12:],
        "stdout_tail": output[-4000:],
        "stderr_tail": errors[-2000:],
        "verified_relation": False,
        "novel_rank": None,
    }
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("w24_source", "normal4_source"),
                        required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = solve(args.policy, args.formula, args.out)
    print(json.dumps({key: result[key] for key in
                      ("policy", "status", "wall_seconds", "guard",
                       "exit_code", "peak_observed_rss_bytes")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
