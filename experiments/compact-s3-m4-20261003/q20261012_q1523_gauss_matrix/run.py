#!/usr/bin/env python3
"""Frozen Gaussian-matrix parameter panel on Q1519 exact S3 handoffs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_fixed_pair_s3_handoff"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
SOURCE = PARENT / "run.py"
SPEC = importlib.util.spec_from_file_location("q1519_handoff", SOURCE)
assert SPEC and SPEC.loader
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)

INPUTS = {
    "n53_known": (53, 8953252913413885,
                  "n53_known_complement_unpinned.xcnf",
                  "7644b17ed9524770d4f03a79b025342eda5e6c63137b6c987563b9d542f2cc7b"),
    "n83_selected": (83, 9493014092419332022685536,
                     "n83_ordinary_selected.xcnf",
                     "9ee183e1a88f6a58f8fa23a73862ec2bf4dc9e5cc26cb7152dac3611ad44f086"),
    "n83_holdout": (83, 3333384481829749803534421,
                    "n83_ordinary_holdout.xcnf",
                    "93be2bebbb594b9d311b3691d630274d6ffcaf7d11e62fb2feff1df9f914361f"),
}
OPTIONS = {
    "default": [],
    "cols4096": ["--maxmatrixcols", "4096"],
    "cols4096_cutoff10": ["--maxmatrixcols", "4096", "--gaussusefulcutoff", "0.1"],
}
EXPECTED_SOLVER = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
EXPECTED_SOURCE = "9e029d3fb3d01dab3faf0fb4bb526458da7ca1edca8118e55d08f63202c850a2"
CPU_CAP = 45
WALL_CAP = 120
CONFLICT_CAP = 2_000_000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(input_name: str, option_name: str) -> None:
    assert sha(SOLVER) == EXPECTED_SOLVER
    assert sha(SOURCE) == EXPECTED_SOURCE
    assert input_name in INPUTS and option_name in OPTIONS
    n, complement, filename, digest = INPUTS[input_name]
    source_formula = PARENT / filename
    assert sha(source_formula) == digest
    run_dir = HERE / "runs" / f"{input_name}_{option_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    command = [str(SOLVER), "--maxtime", str(CPU_CAP),
               "--maxconfl", str(CONFLICT_CAP), "--verb", "1", "--printsol", "1",
               *OPTIONS[option_name], str(source_formula)]
    start_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 errors="replace", timeout=WALL_CAP, check=False)
        stdout, stderr, code, timed_out = process.stdout, process.stderr, process.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
        code, timed_out = None, True
    wall = time.perf_counter() - start
    end_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    (run_dir / "stdout.txt").write_text(stdout)
    (run_dir / "stderr.txt").write_text(stderr)
    matrix_lines = [line for line in stdout.splitlines()
                    if "[matrix]" in line and ("Too many columns" in line
                      or "UNused matrix" in line or "Good matrix" in line
                      or "Using " in line or "disabled" in line.lower())]
    check = None
    if "s SATISFIABLE" in stdout:
        formula, raw, leaves, onb = parent.build(n, complement)
        assert formula.variables == (4246 if n == 53 else 43566)
        values = parent.parse_assignment(stdout, formula.variables)
        check = parent.verify(formula, raw, leaves, onb, complement, values)
    status = ("SAT_VERIFIED" if check else "WALL_CAP" if timed_out else
              "UNSAT" if "s UNSATISFIABLE" in stdout else
              "INDETERMINATE" if "s INDETERMINATE" in stdout else
              "PROCESS_FAILURE" if code not in (0, 10, 20) else "UNKNOWN")
    matches = re.findall(r"^c conflicts\s*:\s*([0-9]+)", stdout, re.I | re.M)
    receipt = {
        "input": input_name, "option": option_name, "status": status,
        "stage": "PDP4sat_fixed_first_pair_S3_handoff", "candidate_id": None,
        "curve_id": "EC1N53Ckb1hf77aab617904" if n == 53 else "EC1N83Ckb1h876c2921cb64",
        "isogeny": "none", "factor_base_B": 24062 if n == 53 else 30977592,
        "effective_columns": 227 if n == 53 else 186612,
        "complement_x_coords": complement, "input_sha256": digest,
        "source_sha256": EXPECTED_SOURCE, "solver_sha256": EXPECTED_SOLVER,
        "command": command, "cpu_cap_seconds": CPU_CAP,
        "wall_cap_seconds": WALL_CAP, "conflict_cap": CONFLICT_CAP,
        "solver_wall_seconds_exploratory": wall,
        "child_user_cpu_seconds": end_usage.ru_utime - start_usage.ru_utime,
        "child_system_cpu_seconds": end_usage.ru_stime - start_usage.ru_stime,
        "child_peak_rss_bytes_darwin": end_usage.ru_maxrss,
        "return_code": code, "matrix_lines": matrix_lines[:30],
        "matrix_line_count": len(matrix_lines),
        "reported_conflicts_last": int(matches[-1]) if matches else None,
        "stdout_sha256": sha(run_dir / "stdout.txt"),
        "stderr_sha256": sha(run_dir / "stderr.txt"), "verification": check,
    }
    (run_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in ("input", "option", "status", "solver_wall_seconds_exploratory", "child_user_cpu_seconds", "reported_conflicts_last", "matrix_lines")}, indent=2))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "usage: python3 run.py INPUT OPTION"
    main(sys.argv[1], sys.argv[2])
